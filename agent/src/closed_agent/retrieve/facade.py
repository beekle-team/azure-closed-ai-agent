from closed_agent.acl import can_read_hit, can_use_skill
from closed_agent.graph.client import GraphClient
from closed_agent.identity import Principal
from closed_agent.retrieve.index import build_index
from closed_agent.retrieve.keyword import KeywordIndex
from closed_agent.retrieve.rrf import fuse
from closed_agent.retrieve.structured import StructuredStore
from closed_agent.retrieve.types import GraphTraversalPolicy, RetrievalHit, RetrievalResult, SearchPlan
from closed_agent.settings import settings
from closed_agent.skills.catalog import SkillCatalog

_MODE_TO_SOURCE = {
    "keyword": "search",
    "vector": "search",
    "graph": "graph",
    "metadata": "structured",
    "skills": "skills",
}


def plan_search(question: str) -> SearchPlan:
    intent, required, targets = _classify(question)
    modes = ["keyword", "graph"]
    policy = GraphTraversalPolicy(start_nodes=["Document", "TacitKnowledge"], max_depth=2)

    if any(word in question for word in ("誰", "ルート", "稟議", "与信", "決裁", "本部長", "財務")):
        modes.append("metadata")
        policy = GraphTraversalPolicy(
            start_nodes=["Person", "Organization"],
            max_depth=3,
            edge_types=["APPROVES", "REPORTS_TO", "GOVERNS"],
        )
    if any(word in question for word in ("出張", "稟議", "契約", "スキル", "口伝", "保険", "投資", "申請")):
        modes.append("skills")
    if intent in {"tacit_lookup", "lesson_lookup", "impact_analysis"}:
        if "vector" not in modes:
            modes.append("vector")

    return SearchPlan(
        question=question,
        intent=intent,
        retrieval_modes=modes,
        required_evidence_type=required,
        target_resource_types=targets,
        graph_traversal_policy=policy,
        filters={"permission_scope": "user-accessible"},
    )


def refine_search_plan(plan: SearchPlan, missing: list[str]) -> SearchPlan:
    modes = list(plan.retrieval_modes)
    for extra in ("keyword", "skills", "metadata", "graph"):
        if extra not in modes:
            modes.append(extra)
    required = plan.required_evidence_type
    if "tacit_knowledge" in missing:
        required = "tacit"
    return SearchPlan(
        question=plan.question,
        intent=plan.intent,
        retrieval_modes=modes,
        required_evidence_type=required,
        target_resource_types=plan.target_resource_types,
        graph_traversal_policy=plan.graph_traversal_policy,
        filters=plan.filters,
        max_results=max(plan.max_results, 12),
        retry_allowed=False,
    )


def _classify(question: str) -> tuple[str, str, list[str]]:
    if any(word in question for word in ("回して", "実行", "動かして")):
        return "skill_run", "skill", ["skill"]
    if any(word in question for word in ("投資", "教訓", "撤退")):
        return "lesson_lookup", "lesson", ["document", "tacit"]
    if any(word in question for word in ("稟議", "与信", "ルート", "決裁", "誰")):
        return "impact_analysis", "route", ["person", "route", "document"]
    if any(word in question for word in ("出張", "保険", "口伝")):
        return "tacit_lookup", "tacit", ["document", "tacit"]
    return "general", "document", ["document"]


class RetrievalFacade:
    """Search Service。計画を受けて全文・グラフ・メタデータ・スキルを足す。"""

    def __init__(
        self,
        graph: GraphClient | None = None,
        keyword: KeywordIndex | None = None,
        structured: StructuredStore | None = None,
        skills: SkillCatalog | None = None,
    ) -> None:
        root = settings.sample_root
        self.graph = graph or GraphClient()
        self.keyword = keyword or build_index(root / "corpus")
        self.structured = structured or StructuredStore(root / "structured.json")
        self.skills = skills or SkillCatalog(root / "skills")

    def search(
        self,
        search_plan: SearchPlan,
        limit: int | None = None,
        principal: Principal | None = None,
    ) -> list[RetrievalHit]:
        return self.retrieve(search_plan, limit=limit, principal=principal).hits

    def retrieve(
        self,
        search_plan: SearchPlan,
        limit: int | None = None,
        principal: Principal | None = None,
    ) -> RetrievalResult:
        cap = limit or search_plan.max_results
        ranked: list[list[RetrievalHit]] = []
        sources = {_MODE_TO_SOURCE.get(mode, mode) for mode in search_plan.retrieval_modes}

        if "graph" in sources:
            ranked.append(self.graph.related(search_plan.question, limit=cap))
        if "search" in sources:
            ranked.append(self.keyword.search(search_plan.question, limit=cap))
        if "structured" in sources:
            ranked.append(self.structured.search(search_plan.question, limit=cap))
        if "skills" in sources:
            skill_hits = []
            for hit in self.skills.as_hits(search_plan.question):
                skill = next((item for item in self.skills.skills if item.name == hit.name), None)
                if principal is None or skill is None or can_use_skill(principal, skill):
                    skill_hits.append(hit)
            ranked.append(skill_hits)

        hits = fuse(ranked)[: max(cap * 3, 12)]
        filtered = False
        if principal is not None:
            hits = [hit for hit in hits if can_read_hit(principal, hit)]
            filtered = True
        hits = hits[:cap]
        missing = _missing_evidence(search_plan, hits)
        confidence = 0.0 if not hits else min(1.0, 0.25 * len(hits) - 0.15 * len(missing))
        action = "answer"
        if missing and search_plan.retry_allowed:
            action = "refine_and_retrieve"
        elif missing and not hits:
            action = "cannot_answer"
        elif missing:
            action = "answer_with_gap"

        return RetrievalResult(
            hits=hits,
            evidence_chunks=[hit for hit in hits if hit.source in {"search", "skills"}],
            graph_paths=[hit.path or hit.reason for hit in hits if hit.source == "graph" and (hit.path or hit.reason)],
            source_references=[f"{hit.source}:{hit.name}" for hit in hits],
            confidence=max(0.0, confidence),
            missing_evidence=missing,
            permission_filtered=filtered,
            recommended_next_action=action,
        )


def _missing_evidence(plan: SearchPlan, hits: list[RetrievalHit]) -> list[str]:
    if not hits:
        return ["any_evidence"]
    kinds = {hit.kind for hit in hits}
    blob = " ".join(f"{hit.name} {hit.reason} {hit.text}" for hit in hits)
    missing: list[str] = []
    required = plan.required_evidence_type
    if required == "tacit" and "TacitKnowledge" not in kinds and "口伝" not in blob:
        missing.append("tacit_knowledge")
    if required == "route" and not kinds.intersection({"Route", "CreditRule", "Person"}):
        missing.append("approval_route")
    if required == "lesson" and "口伝" not in blob and "教訓" not in blob and "TacitKnowledge" not in kinds:
        missing.append("failure_lesson")
    if required == "skill" and "Skill" not in kinds:
        missing.append("skill")
    return missing
