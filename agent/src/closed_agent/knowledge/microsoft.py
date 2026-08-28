from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path

import httpx

from closed_agent.ingest.pipeline import IngestPipeline
from closed_agent.settings import settings

GRAPH = "https://graph.microsoft.com/v1.0"
MAX_BYTES = 200_000


def fixtures_path() -> Path:
    return settings.sample_root / "microsoft" / "items.json"


def load_microsoft_items() -> list[dict[str, str]]:
    path = fixtures_path()
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in payload if item.get("title") and item.get("body")]


def pull_graph_items(token: str, client: httpx.Client | None = None) -> list[dict[str, str]]:
    """OneDrive と SharePoint の本文を取る。フォルダは辿らない。"""
    http = client or httpx.Client(timeout=20.0, follow_redirects=True)
    headers = {"Authorization": f"Bearer {token}"}
    items: list[dict[str, str]] = []
    items.extend(_children(http, headers, f"{GRAPH}/me/drive/root/children", "onedrive"))
    try:
        sites = http.get(f"{GRAPH}/sites", params={"search": "*"}, headers=headers)
        sites.raise_for_status()
        for site in (sites.json().get("value") or [])[:8]:
            site_id = str(site.get("id") or "")
            if not site_id:
                continue
            items.extend(
                _children(
                    http,
                    headers,
                    f"{GRAPH}/sites/{site_id}/drive/root/children",
                    "sharepoint",
                )
            )
    except httpx.HTTPError:
        pass
    return items


def _children(http: httpx.Client, headers: dict[str, str], url: str, source_system: str) -> list[dict[str, str]]:
    response = http.get(url, headers=headers)
    response.raise_for_status()
    items: list[dict[str, str]] = []
    for raw in response.json().get("value") or []:
        name = str(raw.get("name") or "").strip()
        item_id = str(raw.get("id") or "")
        if not name or not item_id or "folder" in raw:
            continue
        web_url = str(raw.get("webUrl") or "")
        parent = raw.get("parentReference") or {}
        drive_id = str(parent.get("driveId") or "")
        body = _download_body(http, headers, item_id, name, drive_id)
        items.append(
            {
                "title": name,
                "kind": "manual",
                "source_system": source_system,
                "source_url": web_url,
                "body": body,
            }
        )
    return items


def _download_body(
    http: httpx.Client,
    headers: dict[str, str],
    item_id: str,
    name: str,
    drive_id: str,
) -> str:
    if drive_id:
        url = f"{GRAPH}/drives/{drive_id}/items/{item_id}/content"
    else:
        url = f"{GRAPH}/me/drive/items/{item_id}/content"
    try:
        response = http.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError:
        return f"Graph の driveItem。名前は {name}。本文の取得に失敗した。"
    return decode_content(name, response.content)


def decode_content(name: str, raw: bytes) -> str:
    payload = raw[:MAX_BYTES]
    lower = name.lower()
    if lower.endswith((".md", ".txt", ".csv", ".json", ".log")):
        return payload.decode("utf-8", errors="replace")
    if lower.endswith((".html", ".htm")):
        text = payload.decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", " ", text)
    if lower.endswith(".docx"):
        return _docx_text(payload) or f"docx の本文が空だった: {name}"
    return f"バイナリ（{name}）。テキストと docx 以外は本文にしない。"


def _docx_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        return ""
    text = re.sub(r"</w:p>", "\n", xml.decode("utf-8", errors="replace"))
    return re.sub(r"<[^>]+>", "", text).strip()


def import_microsoft_knowledge(
    pipeline: IngestPipeline,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, object]:
    existing = {item["name"] for item in pipeline.keyword.catalog()}
    items = load_microsoft_items()
    mode = "fixture"
    graph_token = (token if token is not None else settings.graph_access_token).strip()
    if graph_token:
        try:
            items = pull_graph_items(graph_token, client=client) + items
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
