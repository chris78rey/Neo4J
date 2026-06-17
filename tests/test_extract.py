from neo4j_graphrag.extract import extract_entities, extract_relations, extract_signatures, extract_structured_fields, is_signature_question, is_structured_question
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


def test_extract_signatures():
    text = """
    Elaborado por: Cbop. Marco Ortiz
    Revisado y aprobado por: Tcrn. Juan Carlos Sánchez
    """
    signatures = extract_signatures(text)
    assert signatures["author"] == "Cbop. Marco Ortiz"
    assert signatures["approver"] == "Tcrn. Juan Carlos Sánchez"


def test_signature_question_detection():
    assert is_signature_question("¿Quién firmó el documento?")
    assert is_signature_question("quien aprobó esto")
    assert not is_signature_question("¿De qué trata el documento?")


def test_extract_structured_fields():
    text = """
    Fecha: 10 de Junio 2026
    Institución: HOSPITAL DE ESPECIALIDADES FUERZAS ARMADAS No1
    Nombre del Proyecto: Proyecto X
    Presupuesto referencial (incluido IVA): $ 219.420,00
    Plazo ejecución: 137 días
    """
    fields = extract_structured_fields(text)
    assert fields["date"] == "10 de Junio 2026"
    assert "HOSPITAL DE ESPECIALIDADES FUERZAS ARMADAS" in fields["institution"]
    assert fields["project_name"] == "Proyecto X"
    assert "$ 219.420,00" in fields["budget"]
    assert "137 días" in fields["execution_deadline"]


def test_structured_question_detection():
    assert is_structured_question("¿Cuál es la fecha?")
    assert is_structured_question("¿Cuál es el presupuesto?")
    assert not is_structured_question("¿Qué entidades aparecen?")
