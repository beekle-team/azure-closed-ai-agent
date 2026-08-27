from closed_agent.skills.catalog import SkillCatalog
from closed_agent.skills.runner import run_skill
from closed_agent.settings import settings


def test_catalog_parses_office_skills() -> None:
    catalog = SkillCatalog(settings.sample_root / "skills")
    ids = {skill.id for skill in catalog.skills}
    assert ids == {
        "trip-precheck",
        "ringi-route",
        "contract-review",
        "investment-check",
        "credit-check",
        "trade-docs",
        "compliance-check",
    }


def test_trip_precheck_mentions_insurance() -> None:
    catalog = SkillCatalog(settings.sample_root / "skills")
    skill = catalog.get("trip-precheck")
    assert skill is not None
    answer = run_skill(skill, {"destination": "シンガポール", "days": "8"})
    assert "契約管理部" in answer
    assert "人事" in answer


def test_investment_check_uses_lessons() -> None:
    catalog = SkillCatalog(settings.sample_root / "skills")
    skill = catalog.get("investment-check")
    assert skill is not None
    answer = run_skill(skill, {"target": "デモ食品"})
    assert "論点" in answer or "撤退" in answer


def test_contract_review_needs_approval_flag() -> None:
    catalog = SkillCatalog(settings.sample_root / "skills")
    skill = catalog.get("contract-review")
    assert skill is not None
    assert skill.approval is True


def test_credit_check_sends_first_time_to_credit_desk() -> None:
    catalog = SkillCatalog(settings.sample_root / "skills")
    skill = catalog.get("credit-check")
    assert skill is not None
    answer = run_skill(skill, {"counterparty": "新規取引先", "first_time": "yes"})
    assert "与信室" in answer


def test_trade_docs_stops_on_currency_mismatch() -> None:
    catalog = SkillCatalog(settings.sample_root / "skills")
    skill = catalog.get("trade-docs")
    assert skill is not None
    answer = run_skill(skill, {"invoice_currency": "USD", "bl_currency": "JPY", "incoterms": "FOB"})
    assert "通貨" in answer
    assert "止めて" in answer


def test_compliance_blocks_reexport_letter() -> None:
    catalog = SkillCatalog(settings.sample_root / "skills")
    skill = catalog.get("compliance-check")
    assert skill is not None
    assert skill.approval is True
    answer = run_skill(skill, {"destination": "第三国", "reexport": "yes"})
    assert "該非" in answer
