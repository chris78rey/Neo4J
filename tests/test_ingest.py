from neo4j_graphrag.ingest import chunk_text


def test_chunk_text_overlap():
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=1)
    assert chunks == ["abcd", "defg", "ghij"]
