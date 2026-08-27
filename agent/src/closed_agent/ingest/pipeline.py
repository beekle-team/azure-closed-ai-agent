from pathlib import Path

from closed_agent.graph.client import GraphClient
from closed_agent.retrieve.keyword import KeywordIndex


class IngestPipeline:
    """Blob へ原本を置き、全文とグラフを更新する。Service Bus の代わり。"""

    def __init__(self, corpus_dir: Path, keyword: KeywordIndex, graph: GraphClient | None = None) -> None:
        self.corpus_dir = corpus_dir
        self.keyword = keyword
        self.graph = graph or GraphClient()

    def ingest(self, *, path: str, title: str, body: str, kind: str) -> dict[str, str]:
        self.corpus_dir.mkdir(parents=True, exist_ok=True)
        filename = Path(path).name
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        target = self.corpus_dir / filename
        header = f"# {title}\n\n"
        target.write_text(header + body, encoding="utf-8")
        doc_kind = "TacitKnowledge" if kind == "tacit" else "Document"
        self.keyword.add(title, body, kind=doc_kind)
        self.graph.upsert_document(title, doc_kind)
        return {"path": str(target), "title": title, "kind": doc_kind}
