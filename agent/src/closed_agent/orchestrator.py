from uuid import uuid4

from closed_agent.acl import can_use_skill
from closed_agent.approvals import ApprovalStore, approval_store
from closed_agent.audit import AuditLog, audit_log
from closed_agent.billing import BillingClient, QuotaExceededError
from closed_agent.dlp import scan
from closed_agent.identity import Principal, resolve_principal
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
"""

APPROVAL_WORDS = ("送信", "発注", "削除", "公開")


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


def _needs_approval(question: str) -> bool:
    return any(word in question for word in APPROVAL_WORDS)


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
    channel: str = "web",
) -> ChatResponse:
    billing = billing or BillingClient()
    facade = facade or RetrievalFacade()
    catalog = catalog or facade.skills
    store = approvals or approval_store
    log = audit or audit_log
    actor = principal or resolve_principal(user_id=user_id)
    if actor is None:
        log.record(action="chat", principal=None, resource="chat", outcome="forbidden", detail="unknown identity", channel=channel)
        return ChatResponse(
            status="forbidden",
            answer="身元が確認できないため、答えられません。",
        )

    dlp = scan(question, source="chat")
    if dlp.blocked:
        log.record(action="chat", principal=actor, resource="chat", outcome="blocked", detail=dlp.reason, channel=channel)
        return ChatResponse(
            status="blocked",
            answer="情報取扱規程に触れます。契約書本文・与信の点数・社外秘以上はここでは扱えません。",
        )

    if settings.skip_billing:
        access = {"organization_id": 1, "remaining_tokens": 200000}
    else:
        try:
            access = await billing.access(actor.user_id)
        except QuotaExceededError:
            return ChatResponse(
                status="quota_exceeded",
                answer="今月の利用枠を使い切っています。管理画面でプランを確認してください。",
                remaining_tokens=0,
            )

    search_plan, retrieved = _gather(facade, question, actor)
    hits = retrieved.hits
    citations = _citations(hits)
    context = "\n".join(_evidence_line(hit) for hit in hits) or "- 関係は見つかりませんでした"

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
            return ChatResponse(
                status="forbidden",
                answer=f"スキル「{matched.name}」は {actor.department} では実行できません。",
                remaining_tokens=access["remaining_tokens"],
                skill_id=matched.id,
                plan=search_plan.sources,
                intent=search_plan.intent,
            )
        matched = None

    prior = None
    if approval_id:
        prior = store.get(approval_id)
        if prior is None or prior.user_id != actor.user_id or prior.status not in {"approved", "executed"}:
            prior = None
    if prior is None:
        prior = store.usable_for(principal=actor, question=question, skill_id=matched.id if matched else "")

    if matched and _wants_skill_run(question):
        if (matched.approval or _needs_approval(question)) and prior is None:
            pending = store.create(principal=actor, question=question, skill_id=matched.id)
            log.record(action="approval.create", principal=actor, resource=pending.id, outcome="pending", detail=question, channel=channel)
            return ChatResponse(
                status="needs_approval",
                answer=f"スキル「{matched.name}」は実行前に承認が必要です。",
                citations=citations,
                remaining_tokens=access["remaining_tokens"],
                approval_id=pending.id,
                skill_id=matched.id,
                plan=search_plan.sources,
                intent=search_plan.intent,
                missing_evidence=retrieved.missing_evidence,
                recommended_next_action="ask_approval",
            )
        answer = prior.result if prior and prior.result else run_skill(matched)
        if prior and prior.status == "approved" and not prior.result:
            store.mark_executed(prior.id, answer)
        log.record(action="skill.run", principal=actor, resource=matched.id, outcome="ok", detail=matched.name, channel=channel)
        return ChatResponse(
            status="skill_ran",
            answer=answer,
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            skill_id=matched.id,
            approval_id=prior.id if prior else None,
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="run_skill",
        )

    if _needs_approval(question) and prior is None:
        pending = store.create(principal=actor, question=question, skill_id=matched.id if matched else "")
        log.record(action="approval.create", principal=actor, resource=pending.id, outcome="pending", detail=question, channel=channel)
        return ChatResponse(
            status="needs_approval",
            answer="この操作は実行前に承認が必要です。承認者が通してから続けます。",
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            approval_id=pending.id,
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="ask_approval",
        )

    if retrieved.recommended_next_action == "cannot_answer":
        log.record(action="chat", principal=actor, resource="chat", outcome="cannot_answer", detail=question[:120], channel=channel)
        return ChatResponse(
            status="cannot_answer",
            answer="この身元で見える根拠が足りないので、ここでは答えられません。原本か、担当部署の口伝を足してください。",
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="cannot_answer",
        )

    completion = await complete(
        system=SYSTEM_PROMPT,
        user=f"質問者の部署: {actor.department}\n質問: {question}\n\n根拠:\n{context}",
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
    return ChatResponse(
        status="answered",
        answer=completion.text,
        citations=citations,
        remaining_tokens=remaining,
        skill_id=matched.id if matched else None,
        approval_id=prior.id if prior else None,
        plan=search_plan.sources,
        intent=search_plan.intent,
        missing_evidence=retrieved.missing_evidence,
        recommended_next_action=retrieved.recommended_next_action,
    )
