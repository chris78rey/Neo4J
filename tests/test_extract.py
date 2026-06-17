from neo4j_graphrag.extract import extract_entities, extract_relations
from neo4j_graphrag.ingest import build_chunks, load_document


def test_extract_entities_and_relations(tmp_path):
    path = tmp_path / "doc.txt"
    path.write_text("Neo4j and Qdrant support GraphRAG. We want fewer false positives.", encoding="utf-8")
    document = load_document(str(path))
    chunks = build_chunks(document, chunk_size=100, overlap=0)

    entities = extract_entities(chunks)
    relations = extract_relations(entities)

    names = [entity.name for entity in entities]
    assert "Neo4j" in names
    assert "Qdrant" in names
    assert "We" not in names
    assert relations
    assert relations[0].relation_type == "CO_OCCURS_WITH"
