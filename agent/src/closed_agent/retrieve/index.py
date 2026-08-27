from pathlib import Path

from closed_agent.retrieve.azure_search import AzureSearchClient
from closed_agent.retrieve.keyword import KeywordIndex
from closed_agent.retrieve.types import RetrievalHit


class SyncedIndex(KeywordIndex):
    """手元の全文に加え、設定があれば Azure AI Search へも書く。検索は Azure を先に見る。"""

    def __init__(self, corpus_dir: Path, remote: AzureSearchClient | None = None) -> None:
        super().__init__(corpus_dir)
        self.remote = remote
        self.backend = "azure" if remote is not None else "keyword"
        if self.remote is not None:
            try:
                self.remote.ensure_index()
                for doc in self.docs:
                    self.remote.upsert(doc)
            except Exception:
                self.backend = "keyword"
                self.remote = None

    def add(
        self,
        name: str,
        body: str,
        kind: str = "Document",
        source_system: str = "corpus",
        department: str = "",
        classification: str = "",
        org_wide: bool | None = None,
    ) -> None:
        super().add(
            name,
            body,
            kind=kind,
            source_system=source_system,
            department=department,
            classification=classification,
            org_wide=org_wide,
        )
        if self.remote is None:
            return
        try:
            for doc in self.docs:
                if doc["name"] == name or doc["name"].startswith(f"{name} / "):
                    self.remote.upsert(doc)
        except Exception:
            return

    def search(self, question: str, limit: int = 6) -> list[RetrievalHit]:
        if self.remote is not None:
            try:
                hits = self.remote.search(question, limit=limit)
                if hits:
                    return hits
            except Exception:
                pass
        return super().search(question, limit=limit)


def build_index(corpus_dir: Path) -> KeywordIndex:
    remote = AzureSearchClient.from_settings()
    if remote is None:
        index = KeywordIndex(corpus_dir)
        index.backend = "keyword"  # type: ignore[attr-defined]
        return index
    return SyncedIndex(corpus_dir, remote)


def search_backend(index: KeywordIndex) -> str:
    return getattr(index, "backend", "keyword")
