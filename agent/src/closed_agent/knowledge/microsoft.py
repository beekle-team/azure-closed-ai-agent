from __future__ import annotations

import json
from pathlib import Path

import httpx

from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.settings import settings


def fixtures_path() -> Path:
    return settings.sample_root / "microsoft" / "items.json"


def load_microsoft_items() -> list[dict[str, str]]:
    path = fixtures_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in payload if item.get("title") and item.get("body")]


def pull_graph_items(token: str) -> list[dict[str, str]]:
    """Microsoft Graph の driveItem を口伝と同じ形にする。トークンが無いときは使わない。"""
    response = httpx.get(
        "https://graph.microsoft.com/v1.0/me/drive/root/children",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )
    response.raise_for_status()
    items: list[dict[str, str]] = []
    for raw in response.json().get("value", []):
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        web_url = str(raw.get("webUrl") or "")
        items.append(
            {
                "title": name,
                "kind": "manual",
                "source_system": "onedrive",
                "source_url": web_url,
                "body": f"Graph の driveItem。名前は {name}。本文は Graph の content 取得が必要。",
            }
        )
    return items


def import_microsoft_knowledge(pipeline: IngestPipeline, *, token: str | None = None) -> dict[str, object]:
    existing = {item["name"] for item in pipeline.keyword.catalog()}
    items = load_microsoft_items()
    mode = "fixture"
    graph_token = (token if token is not None else settings.graph_access_token).strip()
    if graph_token:
        try:
            items = pull_graph_items(graph_token) + items
            mode = "graph+fixture"
        except httpx.HTTPError:
            mode = "fixture"

    imported: list[str] = []
    for item in items:
        title = item["title"]
        if title in existing:
            continue
        kind = "TacitKnowledge" if item.get("kind") == "tacit" else "Document"
        source_system = item.get("source_system") or "sharepoint"
        if pipeline.store.kind == "filesystem":
            pipeline.keyword.add(title, item["body"], kind=kind, source_system=source_system)
            pipeline.graph.upsert_document(title, kind)
        else:
            pipeline.ingest(
                path=f"{source_system}-{title}.md",
                title=title,
                body=item["body"],
                kind=item.get("kind") or "manual",
                source_system=source_system,
                source_url=item.get("source_url") or "",
            )
        imported.append(title)
        existing.add(title)
    return {"mode": mode, "imported": imported, "count": len(imported)}
