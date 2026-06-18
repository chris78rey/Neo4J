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


def test_retrieve_context_respects_allowed_document_ids(tmp_path):
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("Oracle APEX modernizes hospital workflows.", encoding="utf-8")
    second_path.write_text("Oracle APEX modernizes hospital workflows.", encoding="utf-8")

    first_document = load_document(str(first_path))
    second_document = load_document(str(second_path))
    first_chunks = build_chunks(first_document, chunk_size=30, overlap=0)
    second_chunks = build_chunks(second_document, chunk_size=30, overlap=0)

    graph_store = InMemoryGraphStore()
    vector_store = InMemoryVectorStore()
    ingest_document(first_document, first_chunks, graph_store, vector_store, model_name="stub")
    ingest_document(second_document, second_chunks, graph_store, vector_store, model_name="stub")

    retrieved = retrieve_context(
        "Oracle APEX modernizes hospital workflows",
        graph_store,
        vector_store,
        allowed_document_ids={second_document.id},
    )

    assert retrieved.chunks
    assert all(item.chunk.document_id == second_document.id for item in retrieved.chunks)


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


def test_compose_answer_returns_concise_fallback():
    from neo4j_graphrag.models import Chunk, Entity
    from neo4j_graphrag.retrieval import RetrievedChunk, RetrievedContext

    retrieved = RetrievedContext(
        chunks=[
            RetrievedChunk(
                chunk=Chunk(
                    id="chunk-1",
                    document_id="doc-1",
                    index=0,
                    text="Oracle APEX moderniza flujos hospitalarios y centraliza reportes.",
                    metadata={"title": "Doc 1"},
                ),
                score=1.25,
            )
        ],
        entities=[Entity(id="entity-1", document_id="doc-1", name="Oracle APEX", entity_type="software")],
    )

    answer = compose_answer("Dame un resumen y dime el beneficio", retrieved, answer_length="short")

    lines = answer.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("Resumen: ")
    assert lines[1].startswith("Beneficio: ")
    assert lines[2].startswith("Evidencia: ")
    assert "Pregunta:" not in answer


def test_compose_answer_returns_long_report_when_requested():
    from neo4j_graphrag.models import Chunk, Entity
    from neo4j_graphrag.retrieval import RetrievedChunk, RetrievedContext

    retrieved = RetrievedContext(
        chunks=[
            RetrievedChunk(
                chunk=Chunk(
                    id="chunk-1",
                    document_id="doc-1",
                    index=0,
                    text="Oracle APEX moderniza flujos hospitalarios y centraliza reportes operativos.",
                    metadata={"title": "Doc 1"},
                ),
                score=1.25,
            ),
            RetrievedChunk(
                chunk=Chunk(
                    id="chunk-2",
                    document_id="doc-1",
                    index=1,
                    text="El sistema mejora trazabilidad, seguimiento de procesos y control de acceso.",
                    metadata={"title": "Doc 1"},
                ),
                score=1.10,
            ),
        ],
        entities=[
            Entity(id="entity-1", document_id="doc-1", name="Oracle APEX", entity_type="software"),
            Entity(id="entity-2", document_id="doc-1", name="Hospital", entity_type="institution"),
        ],
    )

    answer = compose_answer(
        "Necesito un informe detallado de 250 palabras sobre el proyecto",
        retrieved,
        answer_length="long",
        target_words=250,
    )

    assert "Resumen ejecutivo:" in answer
    assert "Desarrollo:" in answer
    assert "Conclusion:" in answer
    assert len(answer.split()) >= 80


def test_broad_question_does_not_surface_unrelated_noise(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text("Neo4j stores graph relationships.", encoding="utf-8")
    document = load_document(str(path))
    chunks = build_chunks(document, chunk_size=30, overlap=0)

    graph_store = InMemoryGraphStore()
    vector_store = InMemoryVectorStore()
    ingest_document(document, chunks, graph_store, vector_store, model_name="stub")

    retrieved = retrieve_context("What is it?", graph_store, vector_store)

    assert retrieved.chunks
    assert retrieved.chunks[0].score <= 1.5
