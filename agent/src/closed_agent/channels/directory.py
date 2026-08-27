"""Teams / メールの差出人を、Laravel の user_id に寄せる。"""

DEFAULT_USERS = {
    "1": 1,
    "admin@example.com": 1,
    "aad-admin": 1,
}


def resolve_user_id(identity: str | None) -> int:
    if not identity:
        return 1
    key = identity.strip().lower()
    if key.isdigit():
        return int(key)
    return DEFAULT_USERS.get(key, 1)
