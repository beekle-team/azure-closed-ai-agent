from neo4j import GraphDatabase

from closed_agent.settings import settings

STATEMENTS = [
    "CREATE FULLTEXT INDEX entityName IF NOT EXISTS FOR (n:Entity) ON EACH [n.name]",
    """
    MERGE (org:Entity:Organization {name: 'デモ組織'})
    MERGE (legal:Entity:Department {name: '法務部'})
    MERGE (it:Entity:Department {name: '情報システム部'})
    MERGE (ops:Entity:Department {name: '営業事務'})
    MERGE (policy:Entity:Policy {name: '情報取扱規程'})
    MERGE (proc:Entity:Procedure {name: '見積作成手順'})
    MERGE (crm:Entity:System {name: '社内CRM'})
    MERGE (org)-[:HAS_DEPARTMENT]->(legal)
    MERGE (org)-[:HAS_DEPARTMENT]->(it)
    MERGE (org)-[:HAS_DEPARTMENT]->(ops)
    MERGE (policy)-[:GOVERNS]->(proc)
    MERGE (policy)-[:GOVERNS]->(crm)
    MERGE (legal)-[:OWNS]->(policy)
    MERGE (ops)-[:USES]->(proc)
    MERGE (ops)-[:USES]->(crm)
    MERGE (it)-[:OPERATES]->(crm)
    MERGE (proc)-[:IMPACTS]->(crm)
    """,
]


def seed() -> None:
    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    with driver.session() as session:
        for statement in STATEMENTS:
            session.run(statement)
    driver.close()


if __name__ == "__main__":
    seed()
    print("seeded graph")
