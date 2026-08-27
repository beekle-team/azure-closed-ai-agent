import json
from pathlib import Path
from typing import Any

from closed_agent.retrieve.types import RetrievalHit


class StructuredStore:
    """PostgreSQL に置く組織・決裁・与信のローカル代替。"""

    def __init__(self, path: Path) -> None:
        self.data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def search(self, question: str, limit: int = 6) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        for person in self.data.get("people", []):
            hay = f"{person['name']} {person['title']} {person['dept']}"
            if any(token in hay or token in question and token in hay for token in _tokens(question)):
                hits.append(
                    RetrievalHit(
                        name=person["name"],
                        kind="Person",
                        reason=f"{person['dept']} {person['title']}",
                        source="structured",
                        text=hay,
                    )
                )
        for route in self.data.get("routes", []):
            if any(token in route["when"] or token in route["name"] for token in _tokens(question)):
                hits.append(
                    RetrievalHit(
                        name=route["name"],
                        kind="Route",
                        reason=route["when"],
                        source="structured",
                        text=route["steps"],
                    )
                )
        for rule in self.data.get("credit_rules", []):
            if any(token in rule["name"] or token in rule["detail"] for token in _tokens(question)):
                hits.append(
                    RetrievalHit(
                        name=rule["name"],
                        kind="CreditRule",
                        reason=rule["detail"],
                        source="structured",
                        text=rule["detail"],
                    )
                )
        return hits[:limit]


def _tokens(question: str) -> list[str]:
    keys = ("出張", "保険", "稟議", "与信", "法務", "営業", "大型", "財務", "人事", "契約", "取引先", "決裁", "本部長")
    found = [key for key in keys if key in question]
    found.extend(part for part in question.replace("　", " ").split() if len(part) >= 2)
    return found
