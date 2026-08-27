from closed_agent.channels.outbound import send_mail
from closed_agent.channels.types import ChannelReply, InboundMessage
from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.orchestrator import run_chat
from closed_agent.retrieve.facade import RetrievalFacade
from closed_agent.schemas import ChatResponse
from closed_agent.settings import settings


async def dispatch(
    message: InboundMessage,
    *,
    facade: RetrievalFacade | None = None,
    ingest: IngestPipeline | None = None,
) -> ChannelReply:
    facade = facade or RetrievalFacade()
    if message.intent == "ingest":
        pipeline = ingest or IngestPipeline(settings.sample_root / "corpus", facade.keyword, facade.graph)
        saved = pipeline.ingest(
            path=f"口伝-{message.title}.md",
            title=message.title or "メールからの口伝",
            body=message.text,
            kind="tacit",
        )
        return _reply(message, f"口伝を文書庫に置いた。{saved['title']}")
    if message.intent == "approve":
        status = "approved" if message.approval_id else "missing_approval_id"
        return _reply(message, f"承認を受け取った。{status} {message.approval_id}".strip())

    response = await run_chat(message.user_id, message.text, facade=facade)
    return _reply(message, _format(response), response)


def _format(response: ChatResponse) -> str:
    if response.status == "needs_approval":
        return f"{response.answer}\n承認ID: {response.approval_id}\nメールか管理画面で承認してください。"
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
