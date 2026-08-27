from typing import Any

from neo4j import GraphDatabase

from closed_agent.settings import settings


class GraphClient:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def related(self, question: str, limit: int = 8) -> list[dict[str, Any]]:
        cypher = """
        CALL db.index.fulltext.queryNodes('entityName', $q) YIELD node, score
        OPTIONAL MATCH (node)-[rel]-(neighbor)
        RETURN node.name AS name,
               labels(node)[0] AS kind,
               type(rel) AS relation,
               neighbor.name AS neighbor,
               labels(neighbor)[0] AS neighbor_kind,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            rows = session.run(cypher, q=self._query(question), limit=limit)
            return [record.data() for record in rows]

    def _query(self, question: str) -> str:
        tokens = [token for token in question.replace("　", " ").split() if len(token) >= 2]
        if not tokens:
            return question
        return " OR ".join(tokens[:8])
