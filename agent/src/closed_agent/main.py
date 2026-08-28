from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from closed_agent.acl import acl_for_ingest, acl_for_item, can_read, can_use_skill, can_write
from closed_agent.approvals import approval_store
from closed_agent.audit import audit_log
from closed_agent.auth import require_auditor, require_principal, require_webhook
from closed_agent.billing import QuotaExceededError
from closed_agent.channels.dispatch import dispatch
from closed_agent.channels.mail import parse_mail
from closed_agent.channels.outbound import OUTBOX, list_inbox
from closed_agent.channels.teams import parse_teams
from closed_agent.conversations import conversation_store
from closed_agent.dlp import scan
from closed_agent.entra import ready as entra_ready
from closed_agent.identity import Principal
from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.knowledge.microsoft import import_microsoft_knowledge
from closed_agent.llm import llm_backend, llm_model
from closed_agent.orchestrator import run_chat
from closed_agent.retrieve.facade import RetrievalFacade, plan_search
from closed_agent.retrieve.index import search_backend
from closed_agent.schemas import (
    ApprovalRequest,
    ChannelReplyResponse,
    ChatRequest,
    ChatResponse,
    IngestRequest,
    MailSendRequest,
    SkillRunRequest,
)
from closed_agent.settings import settings
from closed_agent.skills.runner import run_skill

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Closed AI Agent", version="0.6.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_facade = RetrievalFacade()
_write_root = settings.sample_root / "imported"
_write_root.mkdir(parents=True, exist_ok=True)
_ingest = IngestPipeline(_write_root, _facade.keyword, _facade.graph)
_ingest.hydrate()
import_microsoft_knowledge(_ingest)


def _visible_catalog(principal: Principal) -> list[dict[str, str]]:
    visible = []
    for item in _facade.keyword.catalog():
        if can_read(principal, acl_for_item(item)):
            visible.append(item)
    return visible


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "store": _ingest.store.kind,
        "bus": _ingest.bus.kind,
        "llm": llm_backend(),
        "model": llm_model(),
        "knowledge": len(_facade.keyword.catalog()),
        "app": "/app",
        "auth": settings.auth_mode,
        "entra": entra_ready(),
        "search": search_backend(_facade.keyword),
        "graph": "token" if settings.graph_access_token.strip() else "fixture",
        "version": "0.6.0",
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "closed-agent", "docs": "/docs", "app": "/app"}


@app.get("/app")
def console() -> FileResponse:
    return FileResponse(STATIC_DIR / "console.html")


@app.get("/v1/me")
def me(principal: Principal = Depends(require_principal)) -> dict[str, object]:
    return {
        "user_id": principal.user_id,
        "email": principal.email,
        "name": principal.name,
        "department": principal.department,
        "clearance": principal.clearance,
        "roles": sorted(principal.roles),
        "can_approve": principal.can_approve(),
        "can_audit": principal.can_audit(),
    }


@app.get("/v1/overview")
def overview(principal: Principal = Depends(require_principal)) -> dict[str, object]:
    visible = _visible_catalog(principal)
    sources: dict[str, int] = {}
    departments: dict[str, int] = {}
    for item in visible:
        source = item.get("source_system") or "corpus"
        sources[source] = sources.get(source, 0) + 1
        dept = item.get("department") or "未分類"
        departments[dept] = departments.get(dept, 0) + 1
    pending = [item for item in approval_store.list(principal=principal) if item.status == "pending"]
    return {
        "department": principal.department,
        "visible_knowledge": len(visible),
        "total_knowledge": len(_facade.keyword.catalog()),
        "pending_approvals": len(pending),
        "sources": sources,
        "departments": departments,
        "search": search_backend(_facade.keyword),
    }


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, principal: Principal = Depends(require_principal)) -> ChatResponse:
    try:
        return await run_chat(
            principal.user_id,
            payload.question,
            facade=_facade,
            principal=principal,
            approval_id=payload.approval_id,
            conversation_id=payload.conversation_id,
            channel="web",
        )
    except QuotaExceededError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc


@app.get("/v1/conversations/{conversation_id}")
def get_conversation(conversation_id: str, principal: Principal = Depends(require_principal)) -> dict[str, object]:
    found = conversation_store.get(conversation_id, principal)
    if found is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return found


@app.get("/v1/approvals")
def list_approvals(principal: Principal = Depends(require_principal)) -> list[dict[str, str | int]]:
    return [item.to_dict() for item in approval_store.list(principal=principal)]


@app.post("/v1/approvals/{approval_id}")
async def approve(
    approval_id: str,
    payload: ApprovalRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, str]:
    record = approval_store.get(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval not found")
    if not principal.can_approve():
        audit_log.record(action="approval.decide", principal=principal, resource=approval_id, outcome="forbidden")
        raise HTTPException(status_code=403, detail="承認する権限がありません")
    result = ""
    if payload.approved and record.skill_id:
        skill = _facade.skills.get(record.skill_id)
        if skill:
            result = run_skill(skill)
    decided = approval_store.decide(approval_id, principal=principal, approved=payload.approved, result=result)
    if decided is None:
        raise HTTPException(status_code=404, detail="approval not found")
    if result:
        approval_store.mark_executed(approval_id, result)
        decided = approval_store.get(approval_id) or decided
    audit_log.record(action="approval.decide", principal=principal, resource=approval_id, outcome=decided.status)
    return {
        "approval_id": decided.id,
        "status": decided.status,
        "result": decided.result,
    }


@app.get("/v1/skills")
def list_skills(principal: Principal = Depends(require_principal)) -> list[dict[str, str | bool]]:
    return [
        {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "approval": skill.approval,
        }
        for skill in _facade.skills.skills
        if can_use_skill(principal, skill)
    ]


@app.post("/v1/skills/{skill_id}/run")
def execute_skill(
    skill_id: str,
    payload: SkillRunRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, str]:
    skill = _facade.skills.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    if not can_use_skill(principal, skill):
        raise HTTPException(status_code=403, detail="このスキルを実行する部署ではありません")
    if skill.approval:
        record = approval_store.get(payload.approval_id) if payload.approval_id else None
        if record is None or record.status not in {"approved", "executed"} or record.skill_id != skill.id:
            raise HTTPException(status_code=409, detail="approval required")
    answer = run_skill(skill, payload.inputs)
    if payload.approval_id:
        approval_store.mark_executed(payload.approval_id, answer)
    audit_log.record(action="skill.run", principal=principal, resource=skill.id, outcome="ok")
    return {"skill_id": skill.id, "answer": answer}


@app.get("/v1/search/plan")
def search_plan(q: str, principal: Principal = Depends(require_principal)) -> dict[str, object]:
    plan = plan_search(q)
    payload = plan.to_dict()
    payload["actor_department"] = principal.department
    return payload


@app.get("/v1/knowledge")
def list_knowledge(
    principal: Principal = Depends(require_principal),
    q: str = Query(default=""),
    department: str = Query(default=""),
    classification: str = Query(default=""),
    source_system: str = Query(default=""),
) -> list[dict[str, str]]:
    visible = _visible_catalog(principal)
    needle = q.strip()
    if needle:
        visible = [item for item in visible if needle in item["name"] or needle in (item.get("excerpt") or "")]
    if department:
        visible = [item for item in visible if item.get("department") == department]
    if classification:
        visible = [item for item in visible if item.get("classification") == classification]
    if source_system:
        visible = [item for item in visible if item.get("source_system") == source_system]
    audit_log.record(action="knowledge.list", principal=principal, resource="catalog", outcome="ok", detail=str(len(visible)))
    return visible


@app.get("/v1/knowledge/item")
def get_knowledge(name: str, principal: Principal = Depends(require_principal)) -> dict[str, str]:
    root = name.split(" / ", 1)[0]
    item = _facade.keyword.get(name) or _facade.keyword.get(root)
    if item is None:
        raise HTTPException(status_code=404, detail="knowledge not found")
    if not can_read(principal, acl_for_item(item)):
        audit_log.record(action="knowledge.read", principal=principal, resource=name, outcome="forbidden")
        raise HTTPException(status_code=404, detail="knowledge not found")
    audit_log.record(action="knowledge.read", principal=principal, resource=name, outcome="ok")
    return item


@app.post("/v1/ingest")
def ingest(payload: IngestRequest, principal: Principal = Depends(require_principal)) -> dict[str, str]:
    dlp = scan(f"{payload.title}\n{payload.body}", source="ingest")
    if dlp.blocked:
        audit_log.record(action="ingest", principal=principal, resource=payload.title, outcome="blocked", detail=dlp.reason)
        raise HTTPException(status_code=422, detail=dlp.reason)
    acl = acl_for_ingest(
        title=payload.title,
        kind=payload.kind,
        source_system=payload.source_system,
        principal=principal,
        department=payload.department,
        classification=payload.classification,
        org_wide=payload.org_wide,
    )
    if not can_write(principal, acl):
        raise HTTPException(status_code=403, detail="この部署の文書庫へ書く権限がありません")
    saved = _ingest.ingest(
        path=payload.path,
        title=payload.title,
        body=payload.body,
        kind=payload.kind,
        source_system=payload.source_system,
        source_url=payload.source_url,
        department=acl.department,
        classification=acl.classification,
    )
    audit_log.record(action="ingest", principal=principal, resource=payload.title, outcome="ok")
    return saved


@app.post("/v1/ingest/microsoft")
def ingest_microsoft(principal: Principal = Depends(require_principal)) -> dict[str, object]:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Microsoft 文書の一括取り込みは管理者だけです")
    result = import_microsoft_knowledge(_ingest)
    audit_log.record(action="ingest.microsoft", principal=principal, resource="microsoft", outcome="ok", detail=str(result.get("count")))
    return result


@app.post("/v1/ingest/drain")
def drain_ingest(principal: Principal = Depends(require_principal)) -> dict[str, int]:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="取り込みキューの適用は管理者だけです")
    return {"applied": _ingest.drain()}


@app.post("/v1/channels/teams", response_model=ChannelReplyResponse)
async def teams_channel(
    payload: dict,
    _: None = Depends(require_webhook),
) -> ChannelReplyResponse:
    reply = await dispatch(parse_teams(payload), facade=_facade, ingest=_ingest)
    return ChannelReplyResponse(channel=reply.channel, to=reply.to, text=reply.text, would_send=reply.would_send)


@app.post("/v1/channels/mail", response_model=ChannelReplyResponse)
async def mail_channel(
    payload: dict,
    _: None = Depends(require_webhook),
) -> ChannelReplyResponse:
    reply = await dispatch(parse_mail(payload), facade=_facade, ingest=_ingest)
    return ChannelReplyResponse(channel=reply.channel, to=reply.to, text=reply.text, would_send=reply.would_send)


@app.post("/v1/mail/send", response_model=ChannelReplyResponse)
async def mail_send(payload: MailSendRequest, principal: Principal = Depends(require_principal)) -> ChannelReplyResponse:
    sender = principal.email if not principal.is_admin else (payload.sender or principal.email)
    message = parse_mail(
        {
            "from": sender,
            "subject": payload.subject,
            "body": payload.body,
            "intent": payload.intent or "",
        }
    )
    reply = await dispatch(message, facade=_facade, ingest=_ingest)
    return ChannelReplyResponse(channel=reply.channel, to=reply.to, text=reply.text, would_send=reply.would_send)


@app.get("/v1/mail/outbox")
def mail_outbox(principal: Principal = Depends(require_principal)) -> list[dict[str, str]]:
    if principal.can_audit():
        return OUTBOX[-20:]
    return [item for item in OUTBOX[-20:] if item.get("to") == principal.email]


@app.get("/v1/mail/inbox")
def mail_inbox(principal: Principal = Depends(require_principal)) -> list[dict[str, str]]:
    items = list_inbox()
    if principal.can_audit():
        return items
    return [item for item in items if principal.email in {item.get("from"), item.get("to")}]


@app.get("/v1/audit")
def list_audit(principal: Principal = Depends(require_principal)) -> dict[str, object]:
    require_auditor(principal)
    return {
        "intact": audit_log.intact(),
        "events": audit_log.list(limit=200),
    }
