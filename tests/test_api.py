from fastapi.testclient import TestClient

from neo4j_graphrag.api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["api"] == "ok"


def test_ask_endpoint_with_path():
    response = client.post("/questions?path=requerimientos/00_contexto_general.md", json={"question": "What is it?", "limit": 1})
    assert response.status_code == 200
    assert response.json()["answer"]


def test_ask_endpoint_with_model_override():
    response = client.post(
        "/questions?path=requerimientos/00_contexto_general.md",
        json={
            "question": "What is it?",
            "limit": 1,
            "model": "openai/gpt-4o-mini",
            "embedding_model": "text-embedding-3-large",
        },
    )
    assert response.status_code == 200
    assert response.json()["answer"]


def test_documents_endpoint_returns_job():
    response = client.post(
        "/documents",
        files={"file": ("doc.txt", b"Neo4j and Qdrant support GraphRAG.", "text/plain")},
        data={"embedding_model": "text-embedding-3-large"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]
    assert payload["document_title"]


def test_job_endpoint():
    response = client.get("/jobs/unknown-job")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unknown"


def test_jobs_list_endpoint():
    response = client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_documents_list_endpoint():
    response = client.get("/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_document_detail_endpoint_unknown():
    response = client.get("/documents/unknown")
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == "unknown"
