from pathlib import Path

from closed_agent.azure.bus import MemoryBus, build_bus
from closed_agent.azure.store import MemoryStore, build_store
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
    assert result["store"] == "filesystem"
    assert result["bus"] == "memory"
    assert (tmp_path / "口伝-新しい習慣.md").exists()
    hits = index.search("経理の締日")
    assert hits
    assert graph.last == ("新しい口伝", "TacitKnowledge")


def test_ingest_applies_from_store_after_drain(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("closed_agent.ingest.pipeline.settings.ingest_apply_inline", False)
    index = KeywordIndex(tmp_path)
    graph = SilentGraph()
    store = MemoryStore()
    bus = MemoryBus()
    pipeline = IngestPipeline(tmp_path, index, graph, store=store, bus=bus)  # type: ignore[arg-type]
    result = pipeline.ingest(
        path="口伝-キュー.md",
        title="キュー経由",
        body="原本は文書庫。索引はキューのあと。",
        kind="tacit",
    )
    assert result["store"] == "memory"
    assert result["bus"] == "memory"
    assert index.search("文書庫") == []
    assert pipeline.drain() == 1
    assert index.search("文書庫")
    assert graph.last == ("キュー経由", "TacitKnowledge")
    assert store.get("口伝-キュー.md").startswith("# キュー経由")


def test_local_backends_without_azure_connection(tmp_path: Path) -> None:
    assert build_store(tmp_path).kind == "filesystem"
    assert build_bus().kind == "memory"
