from pathlib import Path

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
        self.docs: list[dict[str, str]] = []
        if corpus_dir.exists():
            for path in sorted(corpus_dir.glob("*.md")):
                self.add(path.stem, path.read_text(encoding="utf-8"), kind=_kind(path.stem))

    def add(self, name: str, body: str, kind: str = "Document") -> None:
        self.docs = [doc for doc in self.docs if doc["name"] != name]
        for chunk in _chunks(name, body, kind):
            self.docs.append(chunk)

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
                )
            )
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:limit]


def _kind(stem: str) -> str:
    return "TacitKnowledge" if stem.startswith("口伝") else "Document"


def _chunks(name: str, body: str, kind: str) -> list[dict[str, str]]:
    parts = [part.strip() for part in body.split("\n## ") if part.strip()]
    if len(parts) <= 1:
        return [{"name": name, "kind": kind, "text": body}]
    chunks = []
    for index, part in enumerate(parts):
        heading = part.split("\n", 1)[0].lstrip("# ").strip()
        chunks.append({"name": f"{name} / {heading}" if index else name, "kind": kind, "text": part})
    return chunks
