from fastapi.testclient import TestClient

from neo4j_graphrag.api import app


client = TestClient(app)


def test_root_is_api_only():
    response = client.get("/")
    assert response.status_code == 404
