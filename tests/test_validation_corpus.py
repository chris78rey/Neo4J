import json
from pathlib import Path

from neo4j_graphrag.connectors import ingest_document
from neo4j_graphrag.ingest import build_chunks, load_document
from neo4j_graphrag.retrieval import get_structured_answer, retrieve_context
from neo4j_graphrag.store import InMemoryGraphStore, InMemoryVectorStore


def test_validation_corpus_ingests_and_answers():
    corpus_path = Path("docs/validation_corpus_oracle.txt")
    document = load_document(str(corpus_path))
    chunks = build_chunks(document, chunk_size=220, overlap=20)
    graph_store = InMemoryGraphStore()
    vector_store = InMemoryVectorStore()

    result = ingest_document(document, chunks, graph_store, vector_store, model_name="stub")

    assert graph_store.count_document_chunks(document.id) == len(chunks)
    assert vector_store.count_document_chunks(document.id) == len(chunks)
    assert result.document.metadata["signatures"]["author"] == "Cbop. Marco Ortiz"
    assert result.document.metadata["structured_fields"]["budget"] == "$ 219.420,00"

    payload = {
        "title": result.document.title,
        "signatures": json.dumps(result.document.metadata["signatures"], ensure_ascii=False),
        "structured_fields": json.dumps(result.document.metadata["structured_fields"], ensure_ascii=False),
    }

    signature_answer = get_structured_answer("¿Quién firmó el documento?", [payload])
    date_answer = get_structured_answer("¿Cuál es la fecha?", [payload])
    budget_answer = get_structured_answer("¿Cuál es el presupuesto del proyecto?", [payload])

    assert signature_answer and "Firmas o roles detectados" in signature_answer
    assert date_answer and "10 de Junio 2026" in date_answer
    assert budget_answer and "$ 219.420,00" in budget_answer

    retrieved = retrieve_context("¿Quién firmó el documento?", graph_store, vector_store)
    assert retrieved.chunks
    assert retrieved.entities
