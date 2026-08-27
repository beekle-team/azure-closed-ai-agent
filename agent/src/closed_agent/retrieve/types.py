from dataclasses import dataclass, field


@dataclass
class RetrievalHit:
    name: str
    kind: str
    reason: str
    source: str
    text: str = ""
    score: float = 0.0
    path: str = ""


@dataclass
class GraphTraversalPolicy:
    start_nodes: list[str]
    max_depth: int = 2
    edge_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str] | int]:
        return {
            "start_nodes": self.start_nodes,
            "max_depth": self.max_depth,
            "edge_types": self.edge_types,
        }


@dataclass
class SearchPlan:
    """Orchestrator が作る検索計画。DB を選ぶのではなく、取り方を書く。"""

    question: str
    intent: str
    retrieval_modes: list[str]
    required_evidence_type: str
    target_resource_types: list[str] = field(default_factory=list)
    graph_traversal_policy: GraphTraversalPolicy | None = None
    filters: dict[str, str] = field(default_factory=dict)
    max_results: int = 8
    retry_allowed: bool = True

    @property
    def sources(self) -> list[str]:
        mapping = {
            "keyword": "search",
            "vector": "search",
            "graph": "graph",
            "metadata": "structured",
            "skills": "skills",
        }
        sources: list[str] = []
        for mode in self.retrieval_modes:
            source = mapping.get(mode, mode)
            if source not in sources:
                sources.append(source)
        return sources

    def to_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "intent": self.intent,
            "retrieval_modes": self.retrieval_modes,
            "required_evidence_type": self.required_evidence_type,
            "target_resource_types": self.target_resource_types,
            "graph_traversal_policy": (
                self.graph_traversal_policy.to_dict() if self.graph_traversal_policy else None
            ),
            "filters": self.filters,
            "max_results": self.max_results,
            "sources": self.sources,
        }


@dataclass
class RetrievalResult:
    """Search Service が Agent に返す統合結果。ヒット一覧だけではない。"""

    hits: list[RetrievalHit]
    evidence_chunks: list[RetrievalHit]
    graph_paths: list[str]
    source_references: list[str]
    confidence: float
    missing_evidence: list[str]
    permission_filtered: bool = False
    recommended_next_action: str = "answer"

    def to_dict(self) -> dict[str, object]:
        return {
            "confidence": self.confidence,
            "missing_evidence": self.missing_evidence,
            "permission_filtered": self.permission_filtered,
            "recommended_next_action": self.recommended_next_action,
            "graph_paths": self.graph_paths,
            "source_references": self.source_references,
            "evidence_chunks": [
                {"name": hit.name, "kind": hit.kind, "source": hit.source, "reason": hit.reason}
                for hit in self.evidence_chunks
            ],
        }
