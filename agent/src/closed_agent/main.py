from fastapi import FastAPI, HTTPException

from closed_agent.agent.loop import run_chat
from closed_agent.billing import QuotaExceededError
from closed_agent.schemas import ApprovalRequest, ChatRequest, ChatResponse

app = FastAPI(title="Closed AI Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    try:
        return await run_chat(payload.user_id, payload.question)
    except QuotaExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc


@app.post("/v1/approvals/{approval_id}")
async def approve(approval_id: str, payload: ApprovalRequest) -> dict[str, str]:
    if not payload.approved:
        return {"approval_id": approval_id, "status": "rejected"}
    return {"approval_id": approval_id, "status": "approved"}
