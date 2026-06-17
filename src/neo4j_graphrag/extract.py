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
