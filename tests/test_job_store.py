from neo4j_graphrag.job_store import FileJobStore


def test_file_job_store_roundtrip(tmp_path):
    path = tmp_path / "jobs.json"
    store = FileJobStore(str(path))
    store.set("job-1", {"status": "running", "detail": "queued"})
    assert store.get("job-1") == {"status": "running", "detail": "queued"}
    assert "job-1" in store.list()
