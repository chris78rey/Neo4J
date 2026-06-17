from neo4j_graphrag.store import InMemoryGraphStore, InMemoryVectorStore


def test_inmemory_probes():
    assert InMemoryGraphStore().probe() == "in-memory graph ok"
    assert InMemoryVectorStore().probe() == "in-memory vector ok"
