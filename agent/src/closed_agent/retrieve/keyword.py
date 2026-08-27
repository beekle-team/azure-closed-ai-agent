from pathlib import Path

from closed_agent.acl import classify
from closed_agent.retrieve.types import RetrievalHit

KEYWORDS = (
    "出張",
    "保険",
    "稟議",
    "与信",
    "法務",
    "営業",
    "大型",
    "契約",
    "口伝",
    "投資",
    "教訓",
    "申請",
    "人事",
    "財務",
    "海外",
    "取引先",
    "決裁",
    "規程",
    "マニュアル",
    "スキル",
    "暗黙知",
    "契約管理",
    "SharePoint",
    "Teams",
    "Outlook",
    "OneDrive",
    "Purview",
    "Graph",
)


def tokenize(text: str) -> set[str]:
    tokens = {word for word in KEYWORDS if word in text}
    stripped = text.replace("　", " ")
    for part in stripped.split():
        if len(part) >= 2:
            tokens.add(part)
    compact = "".join(ch for ch in text if not ch.isspace())
    for index in range(len(compact) - 1):
        pair = compact[index : index + 2]
        if not pair.isascii():
            tokens.add(pair)
    return tokens


class KeywordIndex:
    """Azure AI Search のローカル代替。原本の見出し単位を全文で持つ。"""

    def __init__(self, corpus_dir: Path) -> None:
        self.backend = "keyword"
        self.docs: list[dict[str, str]] = []
        if corpus_dir.exists():
            for path in sorted(corpus_dir.glob("*.md")):
                self.add(path.stem, path.read_text(encoding="utf-8"), kind=_kind(path.stem))

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
        acl = classify(name, kind, source_system)
        meta = {
            "department": department or acl.department,
            "classification": classification or acl.classification,
            "org_wide": acl.org_wide if org_wide is None else org_wide,
        }
        self.docs = [doc for doc in self.docs if doc["name"] != name and not doc["name"].startswith(f"{name} / ")]
        for chunk in _chunks(name, body, kind, source_system):
            chunk.update(meta)
            self.docs.append(chunk)

    def catalog(self) -> list[dict[str, str]]:
        seen: dict[str, dict[str, str]] = {}
        for doc in self.docs:
            root = doc["name"].split(" / ", 1)[0]
            if root in seen:
                continue
            seen[root] = {
                "name": root,
                "kind": doc["kind"],
                "source_system": doc.get("source_system") or "corpus",
                "department": str(doc.get("department") or ""),
                "classification": str(doc.get("classification") or ""),
                "excerpt": doc["text"][:180].replace("\n", " "),
            }
        return list(seen.values())

    def get(self, name: str) -> dict[str, str] | None:
        body = [doc["text"] for doc in self.docs if doc["name"] == name or doc["name"].startswith(f"{name} / ")]
        if not body:
            return None
        first = next(doc for doc in self.docs if doc["name"] == name or doc["name"].startswith(f"{name} / "))
        return {
            "name": name,
            "kind": first["kind"],
            "source_system": first.get("source_system") or "corpus",
            "department": str(first.get("department") or ""),
            "classification": str(first.get("classification") or ""),
            "body": "\n\n".join(body),
        }

    def search(self, question: str, limit: int = 6) -> list[RetrievalHit]:
        query = tokenize(question)
        if not query:
            return []
        scored: list[RetrievalHit] = []
        for doc in self.docs:
            overlap = query & tokenize(f"{doc['name']} {doc['text']}")
            if not overlap:
                continue
            scored.append(
                RetrievalHit(
                    name=doc["name"],
                    kind=doc["kind"],
                    reason="、".join(sorted(overlap)),
                    source="search",
                    text=doc["text"][:400],
                    score=float(len(overlap)),
                    source_system=doc.get("source_system") or "",
                    department=str(doc.get("department") or ""),
                    classification=str(doc.get("classification") or ""),
                    org_wide=bool(doc.get("org_wide")),
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:limit]


def _kind(stem: str) -> str:
    return "TacitKnowledge" if stem.startswith("口伝") else "Document"


def _chunks(name: str, body: str, kind: str, source_system: str = "corpus") -> list[dict[str, str]]:
    parts = [part.strip() for part in body.split("\n## ") if part.strip()]
    if len(parts) <= 1:
        return [{"name": name, "kind": kind, "text": body, "source_system": source_system}]
    chunks = []
    for index, part in enumerate(parts):
        heading = part.split("\n", 1)[0].lstrip("# ").strip()
        chunks.append(
            {
                "name": f"{name} / {heading}" if index else name,
                "kind": kind,
                "text": part,
                "source_system": source_system,
            }
        )
    return chunks
