from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from closed_agent.retrieve.types import RetrievalHit
from closed_agent.settings import settings


class GraphClient:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def related(self, question: str, limit: int = 8) -> list[RetrievalHit]:
        cypher = """
        CALL db.index.fulltext.queryNodes('entityName', $q) YIELD node, score
        OPTIONAL MATCH (node)-[rel]-(neighbor)
        RETURN node.name AS name,
               [label IN labels(node) WHERE label <> 'Entity'][0] AS kind,
               type(rel) AS relation,
               neighbor.name AS neighbor,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        try:
            with self._driver.session() as session:
                rows = session.run(cypher, q=self._query(question), limit=limit)
                hits: list[RetrievalHit] = []
                for record in rows:
                    data: dict[str, Any] = record.data()
                    relation = data.get("relation")
                    neighbor = data.get("neighbor")
                    reason = f"{relation} {neighbor}" if relation and neighbor else "検索ヒット"
                    path = ""
                    if data.get("name") and relation and neighbor:
                        path = f"{data['name']} -> {relation} -> {neighbor}"
                    hits.append(
                        RetrievalHit(
                            name=data.get("name") or "",
                            kind=data.get("kind") or "Entity",
                            reason=reason,
                            source="graph",
                            score=float(data.get("score") or 0),
                            path=path,
                        )
                    )
                return hits
        except (Neo4jError, OSError):
            return []

    def upsert_document(self, name: str, kind: str) -> None:
        label = "TacitKnowledge" if kind == "TacitKnowledge" else "Document"
        cypher = f"""
        MERGE (n:Entity:{label} {{name: $name}})
        WITH n
        OPTIONAL MATCH (org:Entity:Organization)
        FOREACH (_ IN CASE WHEN org IS NULL THEN [] ELSE [1] END |
            MERGE (org)-[:HAS_DOCUMENT]->(n)
        )
        """
        try:
            with self._driver.session() as session:
                session.run(cypher, name=name)
        except (Neo4jError, OSError):
            return

    def _query(self, question: str) -> str:
        tokens = [token for token in question.replace("　", " ").split() if len(token) >= 2]
        extras = [
            word
            for word in ("出張", "保険", "稟議", "与信", "法務", "営業", "大型", "契約", "投資", "教訓")
            if word in question
        ]
        merged = extras + tokens
        if not merged:
            return question
        return " OR ".join(list(dict.fromkeys(merged))[:8])
