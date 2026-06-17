from neo4j_graphrag.store import InMemoryGraphStore, InMemoryVectorStore


def test_inmemory_healthchecks():
    assert InMemoryGraphStore().healthcheck() is True
    assert InMemoryVectorStore().healthcheck() is True
