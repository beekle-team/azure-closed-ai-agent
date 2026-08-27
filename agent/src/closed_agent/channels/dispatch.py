from closed_agent.acl import acl_for_ingest, can_write
from closed_agent.approvals import approval_store
from closed_agent.audit import audit_log
from closed_agent.channels.outbound import send_mail
from closed_agent.channels.types import ChannelReply, InboundMessage
from closed_agent.dlp import scan
from closed_agent.identity import resolve_principal
from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.orchestrator import run_chat
from closed_agent.retrieve.facade import RetrievalFacade
from closed_agent.schemas import ChatResponse
from closed_agent.settings import settings
from closed_agent.skills.catalog import SkillCatalog
from closed_agent.skills.runner import run_skill


async def dispatch(
    message: InboundMessage,
    *,
    facade: RetrievalFacade | None = None,
    ingest: IngestPipeline | None = None,
) -> ChannelReply:
    facade = facade or RetrievalFacade()
    principal = resolve_principal(user_id=message.user_id or None, identity=message.identity)
    if principal is None:
        audit_log.record(
            action="channel.reject",
            principal=None,
            resource=message.channel,
            outcome="forbidden",
            detail=message.identity or "unknown",
            channel=message.channel,
        )
        return _reply(message, "身元が確認できないため、受け付けません。")

    if message.intent == "ingest":
        dlp = scan(message.text, source="ingest")
        if dlp.blocked:
            audit_log.record(action="ingest", principal=principal, resource=message.title, outcome="blocked", detail=dlp.reason, channel=message.channel)
            return _reply(message, "情報取扱規程に触れるため、取り込みませんでした。")
        acl = acl_for_ingest(title=message.title, kind="tacit", source_system=message.channel, principal=principal)
        if not can_write(principal, acl):
            return _reply(message, "この部署の文書庫へ書く権限がありません。")
        pipeline = ingest or IngestPipeline(settings.sample_root / "imported", facade.keyword, facade.graph)
        saved = pipeline.ingest(
            path=f"口伝-{message.title}.md",
            title=message.title or "メールからの口伝",
            body=message.text,
            kind="tacit",
            source_system=message.channel,
            department=acl.department,
            classification=acl.classification,
        )
        audit_log.record(action="ingest", principal=principal, resource=saved["title"], outcome="ok", channel=message.channel)
        return _reply(message, f"口伝を文書庫に置いた。{saved['title']}")

    if message.intent == "approve":
        if not message.approval_id:
            return _reply(message, "承認IDが無いので、受け付けません。")
        if not principal.can_approve():
            return _reply(message, "承認する権限がありません。")
        record = approval_store.decide(message.approval_id, principal=principal, approved=True)
        if record is None:
            return _reply(message, "その承認IDは存在しません。")
        result = record.result
        if record.status == "approved" and record.skill_id:
            skill = SkillCatalog(settings.sample_root / "skills").get(record.skill_id)
            if skill:
                result = run_skill(skill)
                approval_store.mark_executed(record.id, result)
        audit_log.record(action="approval.decide", principal=principal, resource=record.id, outcome=record.status, channel=message.channel)
        return _reply(message, f"承認を記録した。{record.status} {record.id}" + (f"\n{result}" if result else ""))

    response = await run_chat(
        principal.user_id,
        message.text,
        facade=facade,
        principal=principal,
        approval_id=message.approval_id or None,
        channel=message.channel,
    )
    return _reply(message, _format(response), response)


def _format(response: ChatResponse) -> str:
    if response.status == "needs_approval":
        return f"{response.answer}\n承認ID: {response.approval_id}\n承認者のトークンで /v1/approvals を通してください。"
    return response.answer


def _reply(message: InboundMessage, text: str, response: ChatResponse | None = None) -> ChannelReply:
    if message.channel == "teams":
        would = f"Teams の会話 {message.reply_to or '(新規)'} に返す"
    elif message.channel == "mail":
        sent_to = message.reply_to or settings.mail_from
        sent = send_mail(to=sent_to, subject=f"Re: {message.title or '社内AI'}", body=text)
        would = f"{sent['via']} で {sent_to} へ出した"
        if response and response.status == "needs_approval":
            would = f"{sent['via']} で承認依頼を出した"
    else:
        would = "画面に出す"
    return ChannelReply(channel=message.channel, to=message.reply_to, text=text, would_send=would)
