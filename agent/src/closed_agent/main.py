from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from closed_agent.billing import QuotaExceededError
from closed_agent.channels.dispatch import dispatch
from closed_agent.channels.mail import parse_mail
from closed_agent.channels.teams import parse_teams
from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.llm import llm_backend, llm_model
from closed_agent.orchestrator import run_chat
from closed_agent.retrieve.facade import RetrievalFacade, plan_search
from closed_agent.schemas import (
    ApprovalRequest,
    ChannelReplyResponse,
    ChatRequest,
    ChatResponse,
    IngestRequest,
    SkillRunRequest,
)
from closed_agent.settings import settings
from closed_agent.skills.runner import run_skill

app = FastAPI(title="Closed AI Agent", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_facade = RetrievalFacade()
_ingest = IngestPipeline(settings.sample_root / "corpus", _facade.keyword, _facade.graph)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "store": _ingest.store.kind,
        "bus": _ingest.bus.kind,
        "llm": llm_backend(),
        "model": llm_model(),
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "closed-agent", "docs": "/docs"}


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    try:
        return await run_chat(payload.user_id, payload.question, facade=_facade)
    except QuotaExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc


@app.post("/v1/approvals/{approval_id}")
async def approve(approval_id: str, payload: ApprovalRequest) -> dict[str, str]:
    if not payload.approved:
        return {"approval_id": approval_id, "status": "rejected"}
    return {"approval_id": approval_id, "status": "approved"}


@app.get("/v1/skills")
def list_skills() -> list[dict[str, str | bool]]:
    return [
        {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "approval": skill.approval,
        }
        for skill in _facade.skills.skills
    ]


@app.post("/v1/skills/{skill_id}/run")
def execute_skill(skill_id: str, payload: SkillRunRequest) -> dict[str, str]:
    skill = _facade.skills.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    if skill.approval:
        raise HTTPException(status_code=409, detail="approval required")
    return {"skill_id": skill.id, "answer": run_skill(skill, payload.inputs)}


@app.get("/v1/search/plan")
def search_plan(q: str) -> dict[str, object]:
    return plan_search(q).to_dict()


@app.post("/v1/ingest")
def ingest(payload: IngestRequest) -> dict[str, str]:
    return _ingest.ingest(path=payload.path, title=payload.title, body=payload.body, kind=payload.kind)


@app.post("/v1/ingest/drain")
def drain_ingest() -> dict[str, int]:
    return {"applied": _ingest.drain()}


@app.post("/v1/channels/teams", response_model=ChannelReplyResponse)
async def teams_channel(payload: dict) -> ChannelReplyResponse:
    reply = await dispatch(parse_teams(payload), facade=_facade, ingest=_ingest)
    return ChannelReplyResponse(channel=reply.channel, to=reply.to, text=reply.text, would_send=reply.would_send)


@app.post("/v1/channels/mail", response_model=ChannelReplyResponse)
async def mail_channel(payload: dict) -> ChannelReplyResponse:
    reply = await dispatch(parse_mail(payload), facade=_facade, ingest=_ingest)
    return ChannelReplyResponse(channel=reply.channel, to=reply.to, text=reply.text, would_send=reply.would_send)
