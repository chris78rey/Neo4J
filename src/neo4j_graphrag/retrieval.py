from __future__ import annotations

from dataclasses import dataclass

from .extract import extract_entities
from .models import Chunk, Entity
from .store import GraphStore, VectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class RetrievedContext:
    chunks: list[RetrievedChunk]
    entities: list[Entity]


def retrieve(query: str, graph_store: GraphStore, vector_store: VectorStore, limit: int = 3) -> list[RetrievedChunk]:
    candidates = vector_store.search(query, limit=limit)
    if candidates:
        return [RetrievedChunk(chunk=chunk, score=score) for chunk, score in candidates]

    fallback: list[RetrievedChunk] = []
    for chunk in graph_store.list_chunks()[:limit]:
        fallback.append(RetrievedChunk(chunk=chunk, score=0.0))
    return fallback


def retrieve_context(query: str, graph_store: GraphStore, vector_store: VectorStore, limit: int = 3) -> RetrievedContext:
    retrieved_chunks = retrieve(query, graph_store, vector_store, limit=limit)
    entities = extract_entities([item.chunk for item in retrieved_chunks])
    return RetrievedContext(chunks=retrieved_chunks, entities=entities)


def compose_answer(question: str, retrieved: RetrievedContext) -> str:
    lines = [f"Pregunta: {question}", "Contexto recuperado:"]
    for item in retrieved.chunks:
        lines.append(f"- [{item.score:.2f}] {item.chunk.text[:160]}")
    if retrieved.entities:
        lines.append("Entidades detectadas:")
        for entity in retrieved.entities:
            lines.append(f"- {entity.name} ({entity.entity_type})")
    return "\n".join(lines)
