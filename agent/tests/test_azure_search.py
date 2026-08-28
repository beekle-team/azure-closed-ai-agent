import httpx

from closed_agent.retrieve.azure_search import AzureSearchClient
from closed_agent.retrieve.index import SyncedIndex
from closed_agent.retrieve.keyword import KeywordIndex


def test_upsert_and_search_shapes(tmp_path) -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.url.path.endswith("/indexes/corpus") and request.method == "PUT":
            return httpx.Response(201, json={"name": "corpus"})
        if request.url.path.endswith("/docs/index"):
            return httpx.Response(200, json={"value": [{"key": "1", "status": True}]})
        if request.url.path.endswith("/docs/search"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "name": "口伝-出張保険",
                            "kind": "TacitKnowledge",
                            "text": "契約管理部",
                            "source_system": "corpus",
                            "department": "契約管理部",
                            "classification": "confidential",
                            "org_wide": False,
                            "@search.score": 2.5,
                        }
                    ]
                },
            )
        return httpx.Response(404)

    client = AzureSearchClient(
        "https://search.example",
        "key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    client.ensure_index()
    client.upsert({"name": "口伝-出張保険", "text": "保険", "kind": "TacitKnowledge"})
    hits = client.search("出張の保険")
    assert hits[0].name == "口伝-出張保険"
    assert hits[0].source == "search"
    assert any("/indexes/corpus" in url for _, url in calls)
    assert any("/docs/search" in url for _, url in calls)


def test_synced_index_falls_back_when_remote_fails(tmp_path) -> None:
    (tmp_path / "口伝-落ちる.md").write_text("# 口伝\n落ちても手元で探す。", encoding="utf-8")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    remote = AzureSearchClient(
        "https://search.example",
        "key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    index = SyncedIndex(tmp_path, remote)
    assert index.backend == "keyword"
    assert isinstance(index, KeywordIndex)
    assert index.search("手元")
