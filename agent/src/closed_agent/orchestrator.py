from uuid import uuid4

from closed_agent.acl import can_use_skill
from closed_agent.approvals import ApprovalStore, approval_store
from closed_agent.audit import AuditLog, audit_log
from closed_agent.billing import BillingClient, QuotaExceededError
from closed_agent.channels.outbound import send_mail
from closed_agent.conversations import ConversationStore, conversation_store
from closed_agent.dlp import scan
from closed_agent.identity import Principal, resolve_principal
from closed_agent.intent import action_label, detect_action, needs_approval as _needs_approval
from closed_agent.llm import complete, llm_model
from closed_agent.retrieve.facade import RetrievalFacade, plan_search, refine_search_plan
from closed_agent.retrieve.types import RetrievalHit, RetrievalResult, SearchPlan
from closed_agent.schemas import ChatResponse, Citation
from closed_agent.settings import settings
from closed_agent.skills.catalog import SkillCatalog
from closed_agent.skills.runner import run_skill

SYSTEM_PROMPT = """あなたは社内AIチャットです。
渡された関係、原本、口伝、スキルだけを根拠にして答えてください。
関係に無い推測は書かない。実行が必要な操作は承認待ちにします。
口伝はマニュアルより現場の正本として扱います。
根拠が足りないときは、足りないものを書いて止めてください。
渡されていない他部署の口伝は持っていないものとして扱います。
直前の会話は文脈だけに使い、新しい根拠にはしない。
"""


def _mailbox(department: str) -> str:
    mapping: dict[str, str] = {}
    for part in settings.department_mailboxes.split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        mapping[key.strip()] = value.strip()
    return mapping.get(department) or settings.mail_from


def _execute_approved(principal: Principal, question: str, action: str) -> str:
    dest = _mailbox(principal.department)
    label = action_label(action)
    if action in {"send", "publish", "order"}:
        sent = send_mail(
            to=dest,
            subject=f"承認済み: {label}",
            body=f"{principal.email}（{principal.department}）の依頼を実行した。\n\n{question}",
        )
        return f"{label}を実行した。{sent['via']} で {sent['to']} へ出した。"
    if action == "delete":
        return "削除は管理者作業として記録した。原本は文書庫に残している。"
    return f"{label}を記録した。"


def _evidence_line(hit: RetrievalHit) -> str:
    excerpt = (hit.text or hit.reason or hit.path).replace("\n", " ").strip()
    if len(excerpt) > 240:
        excerpt = excerpt[:240] + "…"
    origin = f"{hit.source_system} " if hit.source_system else ""
    return f"- [{hit.source}] {origin}{hit.name} ({hit.kind}) {excerpt}"


def _citations(hits: list[RetrievalHit]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for hit in hits:
        key = f"{hit.source}:{hit.name}"
        if not hit.name or key in seen:
            continue
        seen.add(key)
        citations.append(Citation(name=hit.name, kind=hit.kind, reason=hit.reason, source=hit.source))
    return citations


def _wants_skill_run(question: str) -> bool:
    return any(word in question for word in ("回して", "実行", "動かして"))


def _gather(
    facade: RetrievalFacade,
    question: str,
    principal: Principal | None,
) -> tuple[SearchPlan, RetrievalResult]:
    plan = plan_search(question)
    result = facade.retrieve(plan, principal=principal)
    if result.recommended_next_action == "refine_and_retrieve":
        plan = refine_search_plan(plan, result.missing_evidence)
        result = facade.retrieve(plan, principal=principal)
    return plan, result


def _history_block(messages: list[dict[str, str]]) -> str:
    if not messages:
        return ""
    lines = []
    for item in messages[-6:]:
        lines.append(f"{item.get('role')}: {(item.get('text') or '')[:400]}")
    return "直前の会話:\n" + "\n".join(lines)


async def run_chat(
    user_id: int,
    question: str,
    *,
    billing: BillingClient | None = None,
    facade: RetrievalFacade | None = None,
    catalog: SkillCatalog | None = None,
    principal: Principal | None = None,
    approval_id: str | None = None,
    approvals: ApprovalStore | None = None,
    audit: AuditLog | None = None,
    conversations: ConversationStore | None = None,
    conversation_id: str | None = None,
    channel: str = "web",
) -> ChatResponse:
    billing = billing or BillingClient()
    facade = facade or RetrievalFacade()
    catalog = catalog or facade.skills
    store = approvals or approval_store
    log = audit or audit_log
    convos = conversations or conversation_store
    actor = principal or resolve_principal(user_id=user_id)
    if actor is None:
        log.record(action="chat", principal=None, resource="chat", outcome="forbidden", detail="unknown identity", channel=channel)
        return ChatResponse(
            status="forbidden",
            answer="身元が確認できないため、答えられません。",
        )

    thread_id = conversation_id or ""
    if thread_id:
        existing = convos.get(thread_id, actor)
        if existing is None:
            thread_id = convos.start(actor)
    else:
        thread_id = convos.start(actor)
    convos.append(thread_id, role="user", text=question)

    def _finish(response: ChatResponse) -> ChatResponse:
        response.conversation_id = thread_id
        convos.append(
            thread_id,
            role="assistant",
            text=response.answer,
            status=response.status,
            approval_id=response.approval_id or "",
        )
        return response

    dlp = scan(question, source="chat")
    if dlp.blocked:
        log.record(action="chat", principal=actor, resource="chat", outcome="blocked", detail=dlp.reason, channel=channel)
        return _finish(ChatResponse(
            status="blocked",
            answer="情報取扱規程に触れます。契約書本文・与信の点数・社外秘以上はここでは扱えません。",
        ))

    if settings.skip_billing:
        access = {"organization_id": 1, "remaining_tokens": 200000}
    else:
        try:
            access = await billing.access(actor.user_id)
        except QuotaExceededError:
            return _finish(ChatResponse(
                status="quota_exceeded",
                answer="今月の利用枠を使い切っています。管理画面でプランを確認してください。",
                remaining_tokens=0,
            ))

    search_plan, retrieved = _gather(facade, question, actor)
    hits = retrieved.hits
    citations = _citations(hits)
    context = "\n".join(_evidence_line(hit) for hit in hits) or "- 関係は見つかりませんでした"
    history = _history_block(convos.history(thread_id, limit=7)[:-1])

    matched = catalog.match(question)
    if matched and not can_use_skill(actor, matched):
        if _wants_skill_run(question):
            log.record(
                action="skill.deny",
                principal=actor,
                resource=matched.id,
                outcome="forbidden",
                detail=matched.name,
                channel=channel,
            )
            return _finish(ChatResponse(
                status="forbidden",
                answer=f"スキル「{matched.name}」は {actor.department} では実行できません。",
                remaining_tokens=access["remaining_tokens"],
                skill_id=matched.id,
                plan=search_plan.sources,
                intent=search_plan.intent,
            ))
        matched = None

    prior = None
    if approval_id:
        prior = store.get(approval_id)
        if prior is None or prior.user_id != actor.user_id or prior.status not in {"approved", "executed"}:
            prior = None

    action = detect_action(question) or (prior.action if prior else "")

    if prior and prior.status in {"approved", "executed"}:
        if matched:
            answer = prior.result if prior.result else run_skill(matched)
            if prior.status == "approved" and not prior.result:
                store.mark_executed(prior.id, answer)
            log.record(action="skill.run", principal=actor, resource=matched.id, outcome="ok", detail=matched.name, channel=channel)
            return _finish(ChatResponse(
                status="skill_ran",
                answer=answer,
                citations=citations,
                remaining_tokens=access["remaining_tokens"],
                skill_id=matched.id,
                approval_id=prior.id,
                plan=search_plan.sources,
                intent=search_plan.intent,
                action=action or prior.action,
                missing_evidence=retrieved.missing_evidence,
                recommended_next_action="run_skill",
            ))
        if action or prior.action:
            answer = prior.result or _execute_approved(actor, question, action or prior.action)
            if prior.status == "approved" and not prior.result:
                store.mark_executed(prior.id, answer)
            log.record(action="action.run", principal=actor, resource=prior.id, outcome="ok", detail=action or prior.action, channel=channel)
            return _finish(ChatResponse(
                status="skill_ran",
                answer=answer,
                citations=citations,
                remaining_tokens=access["remaining_tokens"],
                approval_id=prior.id,
                plan=search_plan.sources,
                intent=search_plan.intent,
                action=action or prior.action,
                recommended_next_action="executed",
            ))

    if matched and _wants_skill_run(question):
        if (matched.approval or _needs_approval(question)) and prior is None:
            pending = store.create(principal=actor, question=question, skill_id=matched.id, action=action)
            log.record(action="approval.create", principal=actor, resource=pending.id, outcome="pending", detail=question, channel=channel)
            return _finish(ChatResponse(
                status="needs_approval",
                answer=f"スキル「{matched.name}」は実行前に承認が必要です。",
                citations=citations,
                remaining_tokens=access["remaining_tokens"],
                approval_id=pending.id,
                skill_id=matched.id,
                plan=search_plan.sources,
                intent=search_plan.intent,
                action=action,
                missing_evidence=retrieved.missing_evidence,
                recommended_next_action="ask_approval",
            ))
        answer = run_skill(matched)
        log.record(action="skill.run", principal=actor, resource=matched.id, outcome="ok", detail=matched.name, channel=channel)
        return _finish(ChatResponse(
            status="skill_ran",
            answer=answer,
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            skill_id=matched.id,
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="run_skill",
        ))

    if _needs_approval(question) and prior is None:
        pending = store.create(principal=actor, question=question, skill_id=matched.id if matched else "", action=action)
        log.record(action="approval.create", principal=actor, resource=pending.id, outcome="pending", detail=question, channel=channel)
        return _finish(ChatResponse(
            status="needs_approval",
            answer=f"この{action_label(action) or '操作'}は実行前に承認が必要です。承認者が通してから続けます。",
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            approval_id=pending.id,
            plan=search_plan.sources,
            intent=search_plan.intent,
            action=action,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="ask_approval",
        ))

    if retrieved.recommended_next_action == "cannot_answer":
        log.record(action="chat", principal=actor, resource="chat", outcome="cannot_answer", detail=question[:120], channel=channel)
        return _finish(ChatResponse(
            status="cannot_answer",
            answer="この身元で見える根拠が足りないので、ここでは答えられません。原本か、担当部署の口伝を足してください。",
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="cannot_answer",
        ))

    completion = await complete(
        system=SYSTEM_PROMPT,
        user=f"質問者の部署: {actor.department}\n{history}\n質問: {question}\n\n根拠:\n{context}",
    )
    remaining = access["remaining_tokens"]
    if not settings.skip_billing:
        recorded = await billing.record(
            user_id=actor.user_id,
            organization_id=access["organization_id"],
            request_id=str(uuid4()),
            model=llm_model(),
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
        remaining = recorded["remaining_tokens"]

    log.record(
        action="chat",
        principal=actor,
        resource="chat",
        outcome="answered",
        detail=f"{search_plan.intent}:{len(hits)}",
        channel=channel,
    )
    return _finish(ChatResponse(
        status="answered",
        answer=completion.text,
        citations=citations,
        remaining_tokens=remaining,
        skill_id=matched.id if matched else None,
        plan=search_plan.sources,
        intent=search_plan.intent,
        missing_evidence=retrieved.missing_evidence,
        recommended_next_action=retrieved.recommended_next_action,
        conversation_id=thread_id,
    ))
