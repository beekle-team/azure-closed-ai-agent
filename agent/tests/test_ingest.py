from pathlib import Path

from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.retrieve.keyword import KeywordIndex


class SilentGraph:
    def related(self, question: str, limit: int = 8):
        return []

    def upsert_document(self, name: str, kind: str) -> None:
        self.last = (name, kind)

    def close(self) -> None:
        return


def test_ingest_writes_corpus_and_index(tmp_path: Path) -> None:
    index = KeywordIndex(tmp_path)
    graph = SilentGraph()
    pipeline = IngestPipeline(tmp_path, index, graph)  # type: ignore[arg-type]
    result = pipeline.ingest(
        path="口伝-新しい習慣.md",
        title="新しい口伝",
        body="経理の締日は、画面より半日早い。",
        kind="tacit",
    )
    assert "新しい口伝" in result["title"]
    assert (tmp_path / "口伝-新しい習慣.md").exists()
    hits = index.search("経理の締日")
    assert hits
    assert graph.last == ("新しい口伝", "TacitKnowledge")
