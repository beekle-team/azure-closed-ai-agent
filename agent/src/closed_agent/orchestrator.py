from uuid import uuid4

from closed_agent.billing import BillingClient, QuotaExceededError
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
"""

APPROVAL_WORDS = ("送信", "発注", "削除", "公開")


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


def _gather(facade: RetrievalFacade, question: str) -> tuple[SearchPlan, RetrievalResult]:
    plan = plan_search(question)
    result = facade.retrieve(plan)
    if result.recommended_next_action == "refine_and_retrieve":
        plan = refine_search_plan(plan, result.missing_evidence)
        result = facade.retrieve(plan)
    return plan, result


async def run_chat(
    user_id: int,
    question: str,
    *,
    billing: BillingClient | None = None,
    facade: RetrievalFacade | None = None,
    catalog: SkillCatalog | None = None,
) -> ChatResponse:
    billing = billing or BillingClient()
    facade = facade or RetrievalFacade()
    catalog = catalog or facade.skills
    request_id = str(uuid4())

    if settings.skip_billing:
        access = {"organization_id": 1, "remaining_tokens": 200000}
    else:
        try:
            access = await billing.access(user_id)
        except QuotaExceededError:
            return ChatResponse(
                status="quota_exceeded",
                answer="今月の利用枠を使い切っています。管理画面でプランを確認してください。",
                remaining_tokens=0,
            )

    search_plan, retrieved = _gather(facade, question)
    hits = retrieved.hits
    citations = _citations(hits)
    context = "\n".join(f"- [{hit.source}] {hit.name} ({hit.kind}) {hit.reason}" for hit in hits) or (
        "- 関係は見つかりませんでした"
    )

    matched = catalog.match(question)
    if matched and _wants_skill_run(question):
        if matched.approval or _needs_approval(question):
            return ChatResponse(
                status="needs_approval",
                answer=f"スキル「{matched.name}」は実行前に承認が必要です。",
                citations=citations,
                remaining_tokens=access["remaining_tokens"],
                approval_id=request_id,
                skill_id=matched.id,
                plan=search_plan.sources,
                intent=search_plan.intent,
                missing_evidence=retrieved.missing_evidence,
                recommended_next_action="ask_approval",
            )
        return ChatResponse(
            status="skill_ran",
            answer=run_skill(matched),
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            skill_id=matched.id,
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="run_skill",
        )

    if _needs_approval(question):
        return ChatResponse(
            status="needs_approval",
            answer="この操作は実行前に承認が必要です。管理画面で承認してから続けます。",
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            approval_id=request_id,
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="ask_approval",
        )

    if retrieved.recommended_next_action == "cannot_answer":
        return ChatResponse(
            status="cannot_answer",
            answer="根拠が足りないので、ここでは答えられません。原本か口伝を足してください。",
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            plan=search_plan.sources,
            intent=search_plan.intent,
            missing_evidence=retrieved.missing_evidence,
            recommended_next_action="cannot_answer",
        )

    completion = await complete(
        system=SYSTEM_PROMPT,
        user=f"質問: {question}\n\n根拠:\n{context}",
    )
    remaining = access["remaining_tokens"]
    if not settings.skip_billing:
        recorded = await billing.record(
            user_id=user_id,
            organization_id=access["organization_id"],
            request_id=request_id,
            model=llm_model(),
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
        )
        remaining = recorded["remaining_tokens"]

    return ChatResponse(
        status="answered",
        answer=completion.text,
        citations=citations,
        remaining_tokens=remaining,
        skill_id=matched.id if matched else None,
        plan=search_plan.sources,
        intent=search_plan.intent,
        missing_evidence=retrieved.missing_evidence,
        recommended_next_action=retrieved.recommended_next_action,
    )
