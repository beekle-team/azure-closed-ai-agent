"""Teams / メールの差出人を、社内ディレクトリの user_id に寄せる。未知は 0。"""

from closed_agent.identity import resolve_principal


def resolve_user_id(identity: str | None) -> int:
    principal = resolve_principal(identity=identity)
    return principal.user_id if principal else 0
