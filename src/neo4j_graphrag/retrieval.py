from __future__ import annotations

from dataclasses import dataclass

from .extract import extract_entities
from .models import Chunk, Entity
from .openrouter import OpenRouterConfig, enabled, chat as openrouter_chat
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


def compose_answer(question: str, retrieved: RetrievedContext, model_name: str | None = None) -> str:
    context_lines = [f"- [{item.score:.2f}] {item.chunk.text[:160]}" for item in retrieved.chunks]
    entity_lines = [f"- {entity.name} ({entity.entity_type})" for entity in retrieved.entities]
    if enabled(OpenRouterConfig()) and model_name:
        try:
            prompt = [
                {
                    "role": "system",
                    "content": "You answer questions using the provided context. Be concise and grounded in the context.",
                },
                {
                    "role": "user",
                    "content": "Question:\n"
                    + question
                    + "\n\nContext:\n"
                    + "\n".join(context_lines)
                    + ("\n\nEntities:\n" + "\n".join(entity_lines) if entity_lines else ""),
                },
            ]
            return openrouter_chat(prompt, model=model_name)
        except Exception:
            pass
    lines = [f"Pregunta: {question}", "Contexto recuperado:"]
    lines.extend(context_lines)
    if entity_lines:
        lines.append("Entidades detectadas:")
        lines.extend(entity_lines)
    return "\n".join(lines)
