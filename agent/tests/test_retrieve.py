from closed_agent.retrieve.facade import RetrievalFacade, plan_search, refine_search_plan
from closed_agent.retrieve.keyword import KeywordIndex
from closed_agent.retrieve.rrf import fuse
from closed_agent.retrieve.structured import StructuredStore
from closed_agent.retrieve.types import RetrievalHit
from closed_agent.settings import settings
from closed_agent.skills.catalog import SkillCatalog


class SilentGraph:
    def related(self, question: str, limit: int = 8) -> list[RetrievalHit]:
        return []

    def upsert_document(self, name: str, kind: str) -> None:
        return

    def close(self) -> None:
        return


def test_plan_includes_structured_for_ringi() -> None:
    plan = plan_search("大型稟議は誰に先に話す？")
    assert plan.intent == "impact_analysis"
    assert "metadata" in plan.retrieval_modes
    assert "structured" in plan.sources
    assert "skills" in plan.sources
    assert plan.required_evidence_type == "route"


def test_plan_trip_wants_tacit() -> None:
    plan = plan_search("海外出張の申請、画面に出てこない確認事項は？")
    assert plan.intent == "tacit_lookup"
    assert plan.required_evidence_type == "tacit"


def test_keyword_finds_tacit_insurance() -> None:
    index = KeywordIndex(settings.sample_root / "corpus")
    hits = index.search("海外出張の保険はどこが見る")
    assert any("保険" in hit.name or "保険" in hit.text for hit in hits)


def test_structured_credit_rule() -> None:
    store = StructuredStore(settings.sample_root / "structured.json")
    hits = store.search("初めての取引先の与信ルートは？")
    assert hits
    assert any(hit.kind in {"Route", "CreditRule"} for hit in hits)


def test_rrf_keeps_both_sources() -> None:
    fused = fuse(
        [
            [RetrievalHit("出張保険", "TacitKnowledge", "graph", "graph")],
            [RetrievalHit("出張マニュアル", "Document", "search", "search")],
        ]
    )
    names = {hit.name for hit in fused}
    assert names == {"出張保険", "出張マニュアル"}


def test_retrieve_returns_result_shape() -> None:
    facade = RetrievalFacade(
        graph=SilentGraph(),  # type: ignore[arg-type]
        keyword=KeywordIndex(settings.sample_root / "corpus"),
        structured=StructuredStore(settings.sample_root / "structured.json"),
        skills=SkillCatalog(settings.sample_root / "skills"),
    )
    result = facade.retrieve(plan_search("海外出張の保険はどこが見る"))
    assert result.hits
    assert result.source_references
    assert "tacit_knowledge" not in result.missing_evidence


def test_refine_adds_modes_and_stops_retry() -> None:
    plan = plan_search("見えない手続きは？")
    refined = refine_search_plan(plan, ["any_evidence"])
    assert refined.retry_allowed is False
    assert "skills" in refined.retrieval_modes
    assert "metadata" in refined.retrieval_modes
