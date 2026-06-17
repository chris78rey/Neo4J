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


def test_compose_answer_includes_question():
    from neo4j_graphrag.retrieval import RetrievedContext

    answer = compose_answer("What is Neo4j?", RetrievedContext(chunks=[], entities=[]))
    assert "What is Neo4j?" in answer
