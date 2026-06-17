from __future__ import annotations

import re
from itertools import pairwise

from .models import Chunk, Entity, Relation


ENTITY_PATTERN = re.compile(r"\b([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑ]+)*)\b")
STOPWORDS = {
    "Quiero",
    "Necesito",
    "Respecto",
    "Contexto",
    "Archivo",
    "Documentos",
    "Documento",
    "Pregunta",
    "Contexto",
    "Entidades",
    "Neo4J",
}

SIGNATURE_LABELS = {
    "elaborado por": "author",
    "revisado y aprobado por": "approver",
    "revisado por": "reviewer",
    "aprobado por": "approver",
    "patrocinador del proyecto": "sponsor",
    "líder del proyecto": "project_lead",
    "líder técnico": "technical_lead",
    "responsable del área requirente": "requester",
    "responsable del área adquiriente": "requester",
}

STRUCTURED_FIELD_PATTERNS = {
    "date": re.compile(r"^\s*Fecha:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    "institution": re.compile(r"^\s*Instituci[oó]n:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    "project_name": re.compile(r"^\s*Nombre del Proyecto:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    "budget": re.compile(r"^\s*Presupuesto referencial .*?:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    "execution_deadline": re.compile(r"^\s*Plazo ejecuci[oó]n:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    "warranty": re.compile(r"^\s*Plazo de Garant[ií]a\s*(.+)$", re.IGNORECASE | re.MULTILINE),
}


def extract_entities(chunks: list[Chunk]) -> list[Entity]:
    seen: dict[str, Entity] = {}
    for chunk in chunks:
        for match in ENTITY_PATTERN.finditer(chunk.text):
            name = match.group(1).strip()
            if len(name) < 3:
                continue
            if name in STOPWORDS:
                continue
            if name.isupper() and len(name) <= 4:
                continue
            entity_id = name.lower().replace(" ", "_")
            seen.setdefault(entity_id, Entity(id=entity_id, document_id=chunk.document_id, name=name))
    return list(seen.values())


def extract_relations(entities: list[Entity]) -> list[Relation]:
    relations: list[Relation] = []
    for source, target in pairwise(entities):
        relations.append(
            Relation(
                source_id=source.id,
                target_id=target.id,
                relation_type="CO_OCCURS_WITH",
                confidence=0.5,
            )
        )
    return relations


def extract_signatures(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    signatures: dict[str, str] = {}
    for index, line in enumerate(lines):
        lowered = line.lower()
        for label, key in SIGNATURE_LABELS.items():
            if lowered.startswith(label):
                value = line.split(":", 1)[-1].strip() if ":" in line else ""
                if not value and index + 1 < len(lines):
                    value = lines[index + 1].strip()
                if value:
                    signatures[key] = value
    return signatures


def extract_structured_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, pattern in STRUCTURED_FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def extract_semantic_entities(text: str, document_id: str) -> list[Entity]:
    semantic_entities: list[Entity] = []
    for key, name in extract_signatures(text).items():
        semantic_entities.append(
            Entity(
                id=f"{document_id}:{key}:{name.lower().replace(' ', '_')}",
                document_id=document_id,
                name=name,
                entity_type=key,
            )
        )
    for key, value in extract_structured_fields(text).items():
        semantic_entities.append(
            Entity(
                id=f"{document_id}:{key}:{value.lower().replace(' ', '_')[:60]}",
                document_id=document_id,
                name=value,
                entity_type=key,
            )
        )
    return semantic_entities


def is_signature_question(question: str) -> bool:
    lowered = question.lower()
    markers = [
        "quien firm",
        "quién firm",
        "quien elabor",
        "quién elabor",
        "quien aprob",
        "quién aprob",
        "firmo",
        "firmó",
        "firmante",
        "aprobó",
        "elaboró",
        "suscrib",
    ]
    return any(marker in lowered for marker in markers)


def is_structured_question(question: str) -> bool:
    lowered = question.lower()
    markers = [
        "fecha",
        "instituci",
        "presupuesto",
        "plazo",
        "garant",
        "nombre del proyecto",
        "quién firm",
        "quien firm",
        "quién aprob",
        "quien aprob",
    ]
    return any(marker in lowered for marker in markers)
