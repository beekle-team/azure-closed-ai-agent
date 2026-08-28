from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_BLOCK_PATTERNS = (
    re.compile(r"第\s*[0-9一二三四五六七八九十]+条"),
    re.compile(r"甲\s*(および|及び)\s*乙"),
    re.compile(r"本契約の定め"),
    re.compile(r"契約書本文"),
    re.compile(r"秘密保持契約"),
    re.compile(r"与信点"),
    re.compile(r"与信スコア"),
    re.compile(r"与信枠\s*[:：]?\s*\d"),
    re.compile(r"評点\s*\d"),
    re.compile(r"個人の評価"),
    re.compile(r"クレジットカード番号"),
    re.compile(r"マイナンバー"),
    re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
)

_SECRET_MARKERS = ("社外秘以上", "極秘", "秘匿", "top secret")


@dataclass(frozen=True)
class DlpVerdict:
    blocked: bool
    reason: str = ""


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def scan(text: str, *, source: str = "chat") -> DlpVerdict:
    blob = _normalize(text)
    for pattern in _BLOCK_PATTERNS:
        if pattern.search(blob):
            return DlpVerdict(True, f"{source}: 情報取扱規程で入力禁止の形です")
    if any(marker in blob for marker in _SECRET_MARKERS):
        return DlpVerdict(True, f"{source}: 社外秘以上はチャットにも文書庫APIにも載せない")
    return DlpVerdict(False)
