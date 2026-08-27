from closed_agent.azure.store import MemoryStore
from closed_agent.graph.client import GraphClient
from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.knowledge.microsoft import import_microsoft_knowledge, load_microsoft_items
from closed_agent.retrieve.keyword import KeywordIndex
from closed_agent.retrieve.types import RetrievalHit


class SilentGraph(GraphClient):
    def __init__(self) -> None:
        return

    def related(self, question: str, limit: int = 8) -> list[RetrievalHit]:
        return []

    def upsert_document(self, name: str, kind: str) -> None:
        return

    def close(self) -> None:
        return


def test_microsoft_fixtures_cover_m365_sources() -> None:
    items = load_microsoft_items()
    systems = {item["source_system"] for item in items}
    assert {"sharepoint", "teams", "outlook", "onedrive", "purview"} <= systems


def test_import_microsoft_makes_sharepoint_searchable(tmp_path) -> None:
    index = KeywordIndex(tmp_path)
    pipeline = IngestPipeline(tmp_path, index, SilentGraph(), store=MemoryStore())
    result = import_microsoft_knowledge(pipeline)
    assert result["count"] >= 5
    names = {item["name"] for item in index.catalog()}
    assert "情報取扱規程（SharePoint）" in names
    hits = index.search("SharePoint のリンクを顧客メールに貼ってよいか")
    assert any("SharePoint" in hit.source_system or "Teams" in hit.source_system or "リンク" in hit.text for hit in hits)


def test_hydrate_reloads_store(tmp_path) -> None:
    store = MemoryStore()
    first = IngestPipeline(tmp_path, KeywordIndex(tmp_path), SilentGraph(), store=store)
    first.ingest(path="口伝-保持.md", title="保持の口伝", body="ラベルが付いた文書は個人削除できない。", kind="tacit")
    second = IngestPipeline(tmp_path, KeywordIndex(tmp_path), SilentGraph(), store=store)
    assert second.keyword.search("個人削除") == []
    second.hydrate()
    assert second.keyword.search("個人削除")
