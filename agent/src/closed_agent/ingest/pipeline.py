from pathlib import Path

from closed_agent.azure.bus import IngestBus, build_bus
from closed_agent.azure.store import DocumentStore, build_store
from closed_agent.graph.client import GraphClient
from closed_agent.retrieve.keyword import KeywordIndex
from closed_agent.settings import settings


class IngestPipeline:
    """原本を文書庫へ置き、キュー経由で全文とグラフを更新する。"""

    def __init__(
        self,
        corpus_dir: Path,
        keyword: KeywordIndex,
        graph: GraphClient | None = None,
        store: DocumentStore | None = None,
        bus: IngestBus | None = None,
    ) -> None:
        self.corpus_dir = corpus_dir
        self.keyword = keyword
        self.graph = graph or GraphClient()
        self.store = store or build_store(corpus_dir)
        self.bus = bus or build_bus()

    def ingest(self, *, path: str, title: str, body: str, kind: str) -> dict[str, str]:
        filename = Path(path).name
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        doc_kind = "TacitKnowledge" if kind == "tacit" else "Document"
        stored = self.store.put(filename, f"# {title}\n\n{body}")
        self.bus.send({"path": filename, "title": title, "kind": doc_kind})
        if settings.ingest_apply_inline:
            self.drain()
        return {
            "path": stored,
            "title": title,
            "kind": doc_kind,
            "store": self.store.kind,
            "bus": self.bus.kind,
        }

    def drain(self, limit: int = 8) -> int:
        applied = 0
        for job in self.bus.receive(limit):
            self._apply(job)
            applied += 1
        return applied

    def _apply(self, job: dict[str, str]) -> None:
        text = self.store.get(job["path"])
        body = _body_of(text)
        self.keyword.add(job["title"], body, kind=job["kind"])
        self.graph.upsert_document(job["title"], job["kind"])


def _body_of(text: str) -> str:
    if text.startswith("# "):
        parts = text.split("\n\n", 1)
        if len(parts) == 2:
            return parts[1]
    return text
