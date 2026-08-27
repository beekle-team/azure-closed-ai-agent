from pathlib import Path

from closed_agent.azure.bus import IngestBus, build_bus
from closed_agent.azure.store import DocumentStore, build_store
from closed_agent.graph.client import GraphClient
from closed_agent.ingest.document import parse_stored, render_stored
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

    def ingest(
        self,
        *,
        path: str,
        title: str,
        body: str,
        kind: str,
        source_system: str = "corpus",
        source_url: str = "",
        department: str = "",
        classification: str = "",
    ) -> dict[str, str]:
        filename = Path(path).name
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        doc_kind = "TacitKnowledge" if kind == "tacit" else "Document"
        stored = self.store.put(
            filename,
            render_stored(
                title=title,
                body=body,
                kind=doc_kind,
                source_system=source_system,
                source_url=source_url,
                department=department,
                classification=classification,
            ),
        )
        self.bus.send(
            {
                "path": filename,
                "title": title,
                "kind": doc_kind,
                "source_system": source_system,
            }
        )
        if settings.ingest_apply_inline:
            self.drain()
        return {
            "path": stored,
            "title": title,
            "kind": doc_kind,
            "store": self.store.kind,
            "bus": self.bus.kind,
            "source_system": source_system,
            "department": department,
            "classification": classification,
        }

    def drain(self, limit: int = 8) -> int:
        applied = 0
        for job in self.bus.receive(limit):
            self._apply(job)
            applied += 1
        return applied

    def hydrate(self) -> int:
        applied = 0
        for name, text in self.store.list_documents():
            title, body, meta = parse_stored(text, name)
            kind = meta.get("kind") or ("TacitKnowledge" if title.startswith("口伝") else "Document")
            source_system = meta.get("source_system") or "corpus"
            self.keyword.add(
                title,
                body,
                kind=kind,
                source_system=source_system,
                department=meta.get("department") or "",
                classification=meta.get("classification") or "",
            )
            self.graph.upsert_document(title, kind)
            applied += 1
        return applied

    def _apply(self, job: dict[str, str]) -> None:
        text = self.store.get(job["path"])
        title, body, meta = parse_stored(text, job["path"])
        kind = job.get("kind") or meta.get("kind") or "Document"
        source_system = job.get("source_system") or meta.get("source_system") or "corpus"
        self.keyword.add(
            title or job["title"],
            body,
            kind=kind,
            source_system=source_system,
            department=meta.get("department") or "",
            classification=meta.get("classification") or "",
        )
        self.graph.upsert_document(title or job["title"], kind)
