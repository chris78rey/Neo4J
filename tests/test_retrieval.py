from neo4j_graphrag.connectors import ingest_document
from neo4j_graphrag.ingest import build_chunks, load_document
from neo4j_graphrag.retrieval import compose_answer, retrieve_context
from neo4j_graphrag.store import InMemoryGraphStore, InMemoryVectorStore


def test_retrieve_returns_relevant_chunk(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text("Neo4j stores graph relationships. Qdrant stores vectors.", encoding="utf-8")
    document = load_document(str(path))
    chunks = build_chunks(document, chunk_size=30, overlap=0)
    graph_store = InMemoryGraphStore()
    vector_store = InMemoryVectorStore()
    ingest_document(document, chunks, graph_store, vector_store, model_name="stub")

    retrieved = retrieve_context("graph relationships", graph_store, vector_store)

    assert retrieved.chunks
    assert "graph" in retrieved.chunks[0].chunk.text.lower()
    assert [entity.name for entity in retrieved.entities] == ["Neo4j", "Qdrant"]


def test_retrieve_context_filters_to_document(tmp_path):
    first_path = tmp_path / "neo4j.txt"
    first_path.write_text("Neo4j stores graph relationships.", encoding="utf-8")
    second_path = tmp_path / "oracle.txt"
    second_path.write_text("Oracle APEX modernizes hospital workflows.", encoding="utf-8")

    first_document = load_document(str(first_path))
    second_document = load_document(str(second_path))
    first_chunks = build_chunks(first_document, chunk_size=30, overlap=0)
    second_chunks = build_chunks(second_document, chunk_size=30, overlap=0)

    graph_store = InMemoryGraphStore()
    vector_store = InMemoryVectorStore()
    ingest_document(first_document, first_chunks, graph_store, vector_store, model_name="stub")
    ingest_document(second_document, second_chunks, graph_store, vector_store, model_name="stub")

    retrieved = retrieve_context("modernizes workflows", graph_store, vector_store, document_id=second_document.id)

    assert retrieved.chunks
    assert all(item.chunk.document_id == second_document.id for item in retrieved.chunks)
    assert "oracle" in retrieved.chunks[0].chunk.text.lower()


def test_retrieve_prefers_most_recent_document_when_scores_tie(tmp_path):
    old_path = tmp_path / "old.txt"
    new_path = tmp_path / "new.txt"
    old_path.write_text("Oracle APEX modernizes hospital workflows.", encoding="utf-8")
    new_path.write_text("Oracle APEX modernizes hospital workflows.", encoding="utf-8")

    old_document = load_document(str(old_path))
    new_document = load_document(str(new_path))
    old_chunks = build_chunks(old_document, chunk_size=30, overlap=0)
    new_chunks = build_chunks(new_document, chunk_size=30, overlap=0)

    graph_store = InMemoryGraphStore()
    vector_store = InMemoryVectorStore()
    ingest_document(old_document, old_chunks, graph_store, vector_store, model_name="stub")
    ingest_document(new_document, new_chunks, graph_store, vector_store, model_name="stub")

    retrieved = retrieve_context(
        "Oracle APEX modernizes hospital workflows",
        graph_store,
        vector_store,
        document_metadata={
            old_document.id: {"ingested_at_utc": "2026-06-16T10:00:00+00:00"},
            new_document.id: {"ingested_at_utc": "2026-06-17T10:00:00+00:00"},
        },
    )

    assert retrieved.chunks
    assert retrieved.chunks[0].chunk.document_id == new_document.id


def test_compose_answer_includes_question():
    from neo4j_graphrag.retrieval import RetrievedContext

    answer = compose_answer("What is Neo4j?", RetrievedContext(chunks=[], entities=[]))
    assert "What is Neo4j?" in answer
