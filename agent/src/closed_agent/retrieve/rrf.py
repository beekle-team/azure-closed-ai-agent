from collections import defaultdict

from closed_agent.retrieve.types import RetrievalHit


def fuse(ranked_lists: list[list[RetrievalHit]], k: int = 60) -> list[RetrievalHit]:
    """複数経路の順位を Reciprocal Rank Fusion で足す。"""
    scores: dict[str, float] = defaultdict(float)
    keep: dict[str, RetrievalHit] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits, start=1):
            key = f"{hit.source}:{hit.name}"
            scores[key] += 1.0 / (k + rank)
            if key not in keep:
                keep[key] = hit
    ordered = sorted(keep.values(), key=lambda hit: scores[f"{hit.source}:{hit.name}"], reverse=True)
    for hit in ordered:
        hit.score = scores[f"{hit.source}:{hit.name}"]
    return ordered
