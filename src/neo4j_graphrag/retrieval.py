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


def retrieve(
    query: str,
    graph_store: GraphStore,
    vector_store: VectorStore,
    limit: int = 3,
    document_id: str | None = None,
) -> list[RetrievedChunk]:
    candidates = vector_store.search(query, limit=limit)
    if document_id:
        candidates = [candidate for candidate in candidates if candidate[0].document_id == document_id]
    if candidates:
        return [RetrievedChunk(chunk=chunk, score=score) for chunk, score in candidates]

    fallback: list[RetrievedChunk] = []
    fallback_chunks = graph_store.list_chunks()
    if document_id:
        fallback_chunks = [chunk for chunk in fallback_chunks if chunk.document_id == document_id]
    for chunk in fallback_chunks[:limit]:
        fallback.append(RetrievedChunk(chunk=chunk, score=0.0))
    return fallback


def retrieve_context(
    query: str,
    graph_store: GraphStore,
    vector_store: VectorStore,
    limit: int = 3,
    document_id: str | None = None,
) -> RetrievedContext:
    retrieved_chunks = retrieve(query, graph_store, vector_store, limit=limit, document_id=document_id)
    entities = extract_entities([item.chunk for item in retrieved_chunks])
    return RetrievedContext(chunks=retrieved_chunks, entities=entities)


def looks_english(text: str) -> bool:
    lowered = text.lower()
    english_markers = [
        " the ",
        " and ",
        " project ",
        " database ",
        " answer",
        " involving",
        " management",
    ]
    spanish_markers = [
        " el ",
        " la ",
        " proyecto ",
        " base de datos ",
        " respuesta",
        " involucr",
        " gestión",
    ]
    english_hits = sum(1 for marker in english_markers if marker in lowered)
    spanish_hits = sum(1 for marker in spanish_markers if marker in lowered)
    return english_hits > spanish_hits


def translate_to_spanish(text: str, model_name: str | None = None) -> str:
    if not enabled(OpenRouterConfig()) or not model_name:
        return text
    try:
        prompt = [
            {
                "role": "system",
                "content": "Traduce al español manteniendo el sentido original. No agregues contenido nuevo.",
            },
            {"role": "user", "content": text},
        ]
        return openrouter_chat(prompt, model=model_name)
    except Exception:
        return text


def compose_answer(question: str, retrieved: RetrievedContext, model_name: str | None = None) -> str:
    context_lines = [f"- [{item.score:.2f}] {item.chunk.text[:160]}" for item in retrieved.chunks]
    entity_lines = [f"- {entity.name} ({entity.entity_type})" for entity in retrieved.entities]
    if enabled(OpenRouterConfig()) and model_name:
        try:
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "Responde siempre en español. Si tu borrador sale en inglés, "
                        "traduce toda la respuesta al español antes de devolverla. "
                        "Usa solo el contexto proporcionado, sé breve, claro y no inventes información."
                    ),
                },
                {
                    "role": "user",
                    "content": "Pregunta:\n"
                    + question
                    + "\n\nContexto:\n"
                    + "\n".join(context_lines)
                    + ("\n\nEntidades:\n" + "\n".join(entity_lines) if entity_lines else ""),
                },
            ]
            answer = openrouter_chat(prompt, model=model_name)
            if looks_english(answer):
                answer = translate_to_spanish(answer, model_name=model_name)
            return answer
        except Exception:
            pass
    lines = [f"Pregunta: {question}", "Contexto recuperado:"]
    lines.extend(context_lines)
    if entity_lines:
        lines.append("Entidades detectadas:")
        lines.extend(entity_lines)
    return "\n".join(lines)
