from types import SimpleNamespace

import pytest

from neo4j_graphrag import store as store_module
from neo4j_graphrag.store import InMemoryGraphStore, InMemoryVectorStore


@pytest.mark.parametrize(
    ("builder_name", "cache_name", "status_name", "ctor_name", "fallback_type"),
    [
        ("build_graph_store_from_config", "_GRAPH_STORE", "_GRAPH_STORE_STATUS", "Neo4jGraphStore", InMemoryGraphStore),
        ("build_vector_store_from_config", "_VECTOR_STORE", "_VECTOR_STORE_STATUS", "QdrantVectorStore", InMemoryVectorStore),
    ],
)
def test_remote_store_retries_after_degraded_init(
    monkeypatch,
    builder_name,
    cache_name,
    status_name,
    ctor_name,
    fallback_type,
):
    calls = {"count": 0}

    class FakeRemoteStore:
        def __init__(self, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("temporary outage")

    monkeypatch.setattr(store_module, ctor_name, FakeRemoteStore)
    monkeypatch.setattr(store_module, cache_name, None)
    monkeypatch.setattr(store_module, status_name, "uninitialized")

    config = SimpleNamespace(
        neo4j_uri="neo4j://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        qdrant_url="http://localhost:6333",
        qdrant_api_key="",
        qdrant_collection="graphrag_chunks",
    )

    builder = getattr(store_module, builder_name)
    first_store = builder(config)
    assert isinstance(first_store, fallback_type)
    assert getattr(store_module, status_name).startswith("degraded")

    second_store = builder(config)
    assert isinstance(second_store, FakeRemoteStore)
    assert getattr(store_module, status_name) == "connected"
    assert calls["count"] == 2
