from uuid import uuid4

from closed_agent.billing import BillingClient, QuotaExceededError
from closed_agent.graph.client import GraphClient
from closed_agent.llm import complete
from closed_agent.schemas import ChatResponse, Citation
from closed_agent.settings import settings

SYSTEM_PROMPT = """あなたは閉域の業務エージェントです。
渡されたグラフの関係だけを根拠にして答えてください。
関係に無い推測は書かない。実行が必要な操作は承認待ちにします。
"""


def _citations(rows: list[dict]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for row in rows:
        name = row.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        relation = row.get("relation")
        neighbor = row.get("neighbor")
        reason = f"{relation} {neighbor}" if relation and neighbor else "検索ヒット"
        citations.append(Citation(name=name, kind=row.get("kind") or "Entity", reason=reason))
    return citations


def _needs_approval(question: str) -> bool:
    return any(word in question for word in ("送信", "発注", "削除", "公開"))


async def run_chat(user_id: int, question: str) -> ChatResponse:
    billing = BillingClient()
    graph = GraphClient()
    request_id = str(uuid4())

    try:
        access = await billing.access(user_id)
    except QuotaExceededError:
        return ChatResponse(
            status="quota_exceeded",
            answer="今月の利用枠を使い切っています。管理画面でプランを確認してください。",
            remaining_tokens=0,
        )

    rows = graph.related(question)
    citations = _citations(rows)
    context = "\n".join(
        f"- {row.get('name')} ({row.get('kind')}) {row.get('relation') or ''} {row.get('neighbor') or ''}"
        for row in rows
    ) or "- 関係は見つかりませんでした"

    if _needs_approval(question):
        return ChatResponse(
            status="needs_approval",
            answer="この操作は実行前に承認が必要です。管理画面で承認してから続けます。",
            citations=citations,
            remaining_tokens=access["remaining_tokens"],
            approval_id=request_id,
        )

    completion = await complete(
        system=SYSTEM_PROMPT,
        user=f"質問: {question}\n\n関係:\n{context}",
    )
    recorded = await billing.record(
        user_id=user_id,
        organization_id=access["organization_id"],
        request_id=request_id,
        model=settings.azure_openai_deployment or "mock",
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
    )
    graph.close()

    return ChatResponse(
        status="answered",
        answer=completion.text,
        citations=citations,
        remaining_tokens=recorded["remaining_tokens"],
    )
