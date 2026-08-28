from __future__ import annotations

# 操作の意図。単語の部分一致ではなく、実行系の言い回しを見る。
_ACTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "send",
        (
            "送信して",
            "送って",
            "送付して",
            "メールを出して",
            "メールして",
            "顧客へ送",
            "社外に送",
            "外部に出して",
            "共有して送",
            "貼って送",
        ),
    ),
    ("order", ("発注して", "発注する", "発注をお願い")),
    ("delete", ("削除して", "消して", "廃棄して")),
    ("publish", ("公開して", "外部提供して", "社外に出して", "公開する")),
)


def detect_action(question: str) -> str:
    text = question or ""
    for action, phrases in _ACTIONS:
        if any(phrase in text for phrase in phrases):
            return action
    return ""


def needs_approval(question: str) -> bool:
    return bool(detect_action(question))


def action_label(action: str) -> str:
    return {
        "send": "外部送信",
        "order": "発注",
        "delete": "削除",
        "publish": "公開",
    }.get(action, action or "操作")
