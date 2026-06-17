from neo4j_graphrag.connectors import Pipeline
from neo4j_graphrag.embeddings import build_embeddings
from neo4j_graphrag.ingest import build_chunks, load_document
from neo4j_graphrag.store import InMemoryGraphStore, InMemoryVectorStore


def test_pipeline_ingest_roundtrip(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text("Neo4j works with Qdrant.", encoding="utf-8")
    document = load_document(str(path))
    chunks = build_chunks(document, chunk_size=5, overlap=1)
    embeddings = build_embeddings(chunks, model_name="stub")

    graph_store = InMemoryGraphStore()
    vector_store = InMemoryVectorStore()
    pipeline = Pipeline(graph_store, vector_store)
    result = pipeline.ingest(document, chunks, embeddings)

    assert result.document.id in graph_store.documents
    assert len(graph_store.chunks) == len(chunks)
    assert result.entities
    assert graph_store.entities
    assert result.relations
    assert len(vector_store.records) == len(chunks)
