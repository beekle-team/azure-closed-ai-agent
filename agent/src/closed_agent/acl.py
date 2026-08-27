from __future__ import annotations

from dataclasses import dataclass

from closed_agent.identity import CLEARANCE_RANK, Principal
from closed_agent.retrieve.types import RetrievalHit
from closed_agent.skills.catalog import Skill

ORG_WIDE = "全社"


@dataclass(frozen=True)
class ResourceACL:
    department: str
    classification: str
    org_wide: bool = False


DOCUMENT_ACL: dict[str, ResourceACL] = {
    "出張マニュアル": ResourceACL("人事部", "internal", org_wide=True),
    "情報取扱規程": ResourceACL("法務部", "internal", org_wide=True),
    "情報取扱規程（SharePoint）": ResourceACL("法務部", "internal", org_wide=True),
    "稟議運用": ResourceACL("営業部", "internal", org_wide=True),
    "レコード保持（Purview）": ResourceACL("情報システム部", "restricted", org_wide=False),
    "出張チェックリスト（OneDrive）": ResourceACL("人事部", "internal", org_wide=False),
    "口伝-出張保険": ResourceACL("契約管理部", "confidential"),
    "口伝-与信ルート": ResourceACL("与信室", "confidential"),
    "口伝-大型稟議": ResourceACL("営業部", "confidential"),
    "口伝-投資の失敗": ResourceACL("財務部", "confidential"),
    "口伝-該非は再輸出": ResourceACL("コンプライアンス室", "restricted"),
    "口伝-貿易書類": ResourceACL("貿易管理部", "confidential"),
    "Teams 法務チャネルの口伝": ResourceACL("法務部", "confidential"),
    "Outlook 与信室からの注意": ResourceACL("与信室", "confidential"),
}

PEOPLE_DEPT = {
    "青山 圭一": "営業部",
    "村上 紗季": "財務部",
    "近藤 隼": "与信室",
    "岡田 美穂": "契約管理部",
    "岡田課長": "契約管理部",
    "林 達也": "法務部",
    "中村 結衣": "人事部",
    "斎藤 真": "貿易管理部",
    "藤井 香": "コンプライアンス室",
}

SKILL_DEPARTMENTS: dict[str, set[str]] = {
    "trip-precheck": {"契約管理部", "人事部"},
    "ringi-route": {"営業部", "財務部"},
    "contract-review": {"法務部"},
    "investment-check": {"財務部"},
    "credit-check": {"与信室"},
    "trade-docs": {"貿易管理部"},
    "compliance-check": {"コンプライアンス室"},
}

SKILL_NAME_TO_ID = {
    "出張事前チェック": "trip-precheck",
    "稟議ルート判定": "ringi-route",
    "契約レビュー依頼": "contract-review",
    "事業投資の申請チェック": "investment-check",
    "与信チェック": "credit-check",
    "貿易書類チェック": "trade-docs",
    "コンプラ事前確認": "compliance-check",
}


def classify(name: str, kind: str = "Document", source_system: str = "") -> ResourceACL:
    root = name.split(" / ", 1)[0]
    if root in DOCUMENT_ACL:
        return DOCUMENT_ACL[root]
    if name in PEOPLE_DEPT:
        return ResourceACL(PEOPLE_DEPT[name], "confidential")
    if kind in {"Organization", "Department", "Policy"}:
        return ResourceACL(ORG_WIDE, "internal", org_wide=True)
    if kind == "Person":
        for person, dept in PEOPLE_DEPT.items():
            if person in name or name in person:
                return ResourceACL(dept, "confidential")
        return ResourceACL(ORG_WIDE, "confidential")
    if "与信" in name or source_system == "outlook" and "与信" in name:
        return ResourceACL("与信室", "confidential")
    if "該非" in name or "コンプラ" in name:
        return ResourceACL("コンプライアンス室", "restricted")
    if "貿易" in name or "船積" in name:
        return ResourceACL("貿易管理部", "confidential")
    if "保険" in name or "契約管理" in name:
        return ResourceACL("契約管理部", "confidential")
    if "投資" in name or "財務" in name:
        return ResourceACL("財務部", "confidential")
    if "大型稟議" in name:
        return ResourceACL("営業部", "confidential")
    if "法務" in name or source_system == "teams" and "法務" in name:
        return ResourceACL("法務部", "confidential")
    if "出張" in name:
        return ResourceACL("人事部", "internal", org_wide=kind != "TacitKnowledge")
    if "規程" in name:
        return ResourceACL("法務部", "internal", org_wide=True)
    if source_system == "purview":
        return ResourceACL("情報システム部", "restricted")
    if kind == "TacitKnowledge" or "口伝" in name:
        return ResourceACL("情報システム部", "restricted", org_wide=False)
    if kind == "CreditRule" or kind == "Route" and "与信" in name:
        return ResourceACL("与信室", "confidential")
    if kind == "Route":
        return ResourceACL("営業部", "internal")
    if kind == "Skill":
        skill_id = SKILL_NAME_TO_ID.get(root, "")
        depts = SKILL_DEPARTMENTS.get(skill_id, set())
        department = next(iter(depts), ORG_WIDE)
        return ResourceACL(department, "internal")
    return ResourceACL(ORG_WIDE, "internal", org_wide=True)


def classify_hit(hit: RetrievalHit) -> ResourceACL:
    if hit.department:
        return ResourceACL(
            hit.department,
            hit.classification or "confidential",
            hit.org_wide,
        )
    return classify(hit.name, hit.kind, hit.source_system)


def can_read(principal: Principal, acl: ResourceACL) -> bool:
    if principal.is_admin:
        return True
    if principal.clearance_rank() < CLEARANCE_RANK.get(acl.classification, 0):
        return False
    if acl.org_wide:
        return True
    return acl.department in {principal.department, ORG_WIDE}


def can_read_hit(principal: Principal, hit: RetrievalHit) -> bool:
    return can_read(principal, classify_hit(hit))


def can_write(principal: Principal, acl: ResourceACL) -> bool:
    if principal.is_admin:
        return True
    if principal.clearance_rank() < CLEARANCE_RANK.get(acl.classification, 0):
        return False
    return acl.department == principal.department


def can_use_skill(principal: Principal, skill: Skill) -> bool:
    if principal.is_admin:
        return True
    allowed = SKILL_DEPARTMENTS.get(skill.id, set())
    return principal.department in allowed


def acl_for_ingest(*, title: str, kind: str, source_system: str, principal: Principal) -> ResourceACL:
    guessed = classify(title, "TacitKnowledge" if kind == "tacit" else "Document", source_system)
    if principal.is_admin:
        return guessed
    classification = "confidential" if kind == "tacit" else "internal"
    return ResourceACL(principal.department, classification, org_wide=False)
