from __future__ import annotations

import hashlib
import re
from typing import Any

import httpx

from closed_agent.retrieve.types import RetrievalHit
from closed_agent.settings import settings

API_VERSION_DEFAULT = "2024-07-01"


def _key(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()


class AzureSearchClient:
    """Azure AI Search の REST クライアント。エンドポイントが空なら使わない。"""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        index_name: str = "corpus",
        api_version: str = API_VERSION_DEFAULT,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.index_name = index_name
        self.api_version = api_version
        self._http = client or httpx.Client(timeout=15.0)
        self.kind = "azure"

    @classmethod
    def from_settings(cls) -> AzureSearchClient | None:
        endpoint = settings.azure_search_endpoint.strip()
        key = settings.azure_search_api_key.strip()
        if not endpoint or not key:
            return None
        return cls(
            endpoint=endpoint,
            api_key=key,
            index_name=settings.azure_search_index or "corpus",
            api_version=settings.azure_search_api_version or API_VERSION_DEFAULT,
        )

    def _headers(self) -> dict[str, str]:
        return {"api-key": self.api_key, "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.endpoint}{path}?api-version={self.api_version}"

    def ensure_index(self) -> None:
        payload = {
            "name": self.index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
                {"name": "name", "type": "Edm.String", "searchable": True, "filterable": True},
                {"name": "text", "type": "Edm.String", "searchable": True},
                {"name": "kind", "type": "Edm.String", "filterable": True, "facetable": True},
                {"name": "source_system", "type": "Edm.String", "filterable": True, "facetable": True},
                {"name": "department", "type": "Edm.String", "filterable": True, "facetable": True},
                {"name": "classification", "type": "Edm.String", "filterable": True},
                {"name": "org_wide", "type": "Edm.Boolean", "filterable": True},
            ],
        }
        response = self._http.put(
            self._url(f"/indexes/{self.index_name}"),
            headers=self._headers(),
            json=payload,
        )
        if response.status_code not in {200, 201, 204}:
            response.raise_for_status()

    def upsert(self, doc: dict[str, Any]) -> None:
        body = {
            "value": [
                {
                    "@search.action": "mergeOrUpload",
                    "id": _key(str(doc["name"])),
                    "name": doc["name"],
                    "text": doc.get("text") or "",
                    "kind": doc.get("kind") or "Document",
                    "source_system": doc.get("source_system") or "corpus",
                    "department": str(doc.get("department") or ""),
                    "classification": str(doc.get("classification") or ""),
                    "org_wide": bool(doc.get("org_wide")),
                }
            ]
        }
        response = self._http.post(
            self._url(f"/indexes/{self.index_name}/docs/index"),
            headers=self._headers(),
            json=body,
        )
        response.raise_for_status()

    def search(self, question: str, limit: int = 6) -> list[RetrievalHit]:
        query = _escape(question)
        response = self._http.post(
            self._url(f"/indexes/{self.index_name}/docs/search"),
            headers=self._headers(),
            json={"search": query, "top": limit, "queryType": "simple"},
        )
        response.raise_for_status()
        hits: list[RetrievalHit] = []
        for item in response.json().get("value", []):
            hits.append(
                RetrievalHit(
                    name=str(item.get("name") or ""),
                    kind=str(item.get("kind") or "Document"),
                    reason="azure-search",
                    source="search",
                    text=str(item.get("text") or "")[:400],
                    score=float(item.get("@search.score") or 0),
                    source_system=str(item.get("source_system") or ""),
                    department=str(item.get("department") or ""),
                    classification=str(item.get("classification") or ""),
                    org_wide=bool(item.get("org_wide")),
                )
            )
        return hits


def _escape(question: str) -> str:
    cleaned = re.sub(r"[+\-&|!(){}^\"~*?:\\/]", " ", question).strip()
    return cleaned or "*"
