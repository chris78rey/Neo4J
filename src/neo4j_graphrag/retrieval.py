from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass

from .extract import extract_entities, is_signature_question
from .models import Chunk, Entity
from .openrouter import OpenRouterConfig, enabled, chat as openrouter_chat
from .store import GraphStore, VectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float
    origin: str = "graph"


@dataclass(frozen=True)
class RetrievedContext:
    chunks: list[RetrievedChunk]
    entities: list[Entity]
    related_documents: list[str] | None = None


def _query_tokens(query: str) -> set[str]:
    return {token.lower().strip(".,;:()[]{}") for token in query.split() if token.strip()}


def _chunk_tokens(chunk_text: str) -> set[str]:
    return _query_tokens(chunk_text)


def _entity_hit_score(query: str, entity_name: str) -> float:
    lowered_query = query.lower()
    entity_lower = entity_name.lower()
    if entity_lower in lowered_query:
        return 2.0
    tokens = _query_tokens(query)
    if any(token in entity_lower for token in tokens):
        return 1.0
    return 0.0


def _token_overlap_score(query: str, text: str) -> float:
    query_tokens = _query_tokens(query)
    if not query_tokens:
        return 0.0
    text_tokens = _chunk_tokens(text)
    if not text_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    return overlap / len(query_tokens)


def _document_recency_score(document_meta: dict[str, str] | None) -> float:
    if not document_meta:
        return 0.0
    raw_timestamp = document_meta.get("ingested_at_utc") or document_meta.get("ingested_at_ecuador")
    if not raw_timestamp:
        return 0.0
    try:
        timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age_seconds = max((datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds(), 0.0)
    age_hours = age_seconds / 3600.0
    return 1.0 / (1.0 + (age_hours / 24.0))


def _question_type_weights(question: str) -> dict[str, float]:
    lowered = question.lower()
    if is_signature_question(question):
        return {"embedding": 0.8, "graph": 0.25, "recency": 0.1, "overlap": 0.2, "penalty": 0.25}
    if any(key in lowered for key in ["fecha", "instituci", "presupuesto", "plazo", "garant", "proyecto"]):
        return {"embedding": 0.9, "graph": 0.2, "recency": 0.25, "overlap": 0.2, "penalty": 0.2}
    if any(key in lowered for key in ["quién", "quien", "actor", "fase", "responsable"]):
        return {"embedding": 0.85, "graph": 0.3, "recency": 0.15, "overlap": 0.15, "penalty": 0.2}
    return {"embedding": 1.0, "graph": 0.2, "recency": 0.2, "overlap": 0.15, "penalty": 0.3}


def retrieve(
    query: str,
    graph_store: GraphStore,
    vector_store: VectorStore,
    limit: int = 3,
    document_id: str | None = None,
    document_metadata: dict[str, dict[str, str]] | None = None,
) -> list[RetrievedChunk]:
    vector_candidates = vector_store.search(query, limit=max(limit, 5))
    if document_id:
        vector_candidates = [candidate for candidate in vector_candidates if candidate[0].document_id == document_id]

    relevant_entities = [
        entity
        for entity in graph_store.list_entities()
        if entity.document_id and _entity_hit_score(query, entity.name) > 0
    ]
    relevant_document_ids = {entity.document_id for entity in relevant_entities}

    graph_chunks = graph_store.list_chunks()
    if document_id:
        graph_chunks = [chunk for chunk in graph_chunks if chunk.document_id == document_id]
    elif relevant_document_ids:
        graph_chunks = [chunk for chunk in graph_chunks if chunk.document_id in relevant_document_ids]

    scored: dict[str, RetrievedChunk] = {}
    weights = _question_type_weights(query)
    for chunk, score in vector_candidates:
        if document_id and chunk.document_id != document_id:
            continue
        metadata = document_metadata.get(chunk.document_id, {}) if document_metadata else {}
        recency_boost = _document_recency_score(metadata)
        overlap = _token_overlap_score(query, chunk.text)
        graph_signal = 1.0 if relevant_document_ids and chunk.document_id in relevant_document_ids else 0.0
        irrelevance_penalty = weights["penalty"] if overlap == 0 else max(0.0, weights["penalty"] - overlap)
        combined_score = (
            score * weights["embedding"]
            + (weights["graph"] * graph_signal)
            + (weights["recency"] * recency_boost)
            + (weights["overlap"] * overlap)
            - irrelevance_penalty
        )
        scored[chunk.id] = RetrievedChunk(chunk=chunk, score=combined_score, origin="embeddings+graph")

    for chunk in graph_chunks:
        if chunk.id in scored:
            continue
        metadata = document_metadata.get(chunk.document_id, {}) if document_metadata else {}
        recency_boost = _document_recency_score(metadata)
        overlap = _token_overlap_score(query, chunk.text)
        graph_signal = 1.0 if relevant_document_ids and chunk.document_id in relevant_document_ids else 0.0
        irrelevance_penalty = weights["penalty"] * 0.7 if overlap == 0 else max(0.0, (weights["penalty"] * 0.6) - overlap)
        base_score = (weights["graph"] * graph_signal) + (weights["recency"] * recency_boost) + (weights["overlap"] * overlap)
        base_score -= irrelevance_penalty
        scored[chunk.id] = RetrievedChunk(chunk=chunk, score=base_score, origin="graph")

    ranked = sorted(
        scored.values(),
        key=lambda item: (item.score, item.chunk.index),
        reverse=True,
    )
    if ranked:
        return ranked[:limit]

    fallback: list[RetrievedChunk] = []
    for chunk in graph_store.list_chunks()[:limit]:
        fallback.append(RetrievedChunk(chunk=chunk, score=0.0, origin="fallback"))
    return fallback


def retrieve_context(
    query: str,
    graph_store: GraphStore,
    vector_store: VectorStore,
    limit: int = 3,
    document_id: str | None = None,
    document_metadata: dict[str, dict[str, str]] | None = None,
) -> RetrievedContext:
    retrieved_chunks = retrieve(
        query,
        graph_store,
        vector_store,
        limit=limit,
        document_id=document_id,
        document_metadata=document_metadata,
    )
    entities = extract_entities([item.chunk for item in retrieved_chunks])
    graph_entities = graph_store.list_entities()
    graph_relations = graph_store.list_relations()
    seen_ids = {entity.id for entity in entities}
    retrieved_document_ids = {chunk.chunk.document_id for chunk in retrieved_chunks}
    for entity in graph_entities:
        if entity.document_id and entity.id not in seen_ids:
            if entity.document_id in retrieved_document_ids:
                entities.append(entity)
                seen_ids.add(entity.id)
    related_documents: list[str] = []
    retrieved_entity_ids = {entity.id for entity in entities}
    for relation in graph_relations:
        if relation.source_id in retrieved_entity_ids or relation.target_id in retrieved_entity_ids:
            for entity in graph_entities:
                if entity.id == relation.source_id:
                    related_documents.append(entity.document_id)
                if entity.id == relation.target_id:
                    related_documents.append(entity.document_id)
    related_documents = [doc for doc in dict.fromkeys(related_documents) if doc not in retrieved_document_ids]
    return RetrievedContext(chunks=retrieved_chunks, entities=entities, related_documents=related_documents)


def explain_retrieval(context: RetrievedContext) -> list[str]:
    lines: list[str] = []
    for item in context.chunks:
        lines.append(
            f"- {item.chunk.document_id}#{item.chunk.index} score={item.score:.2f} origin={item.origin} source={item.chunk.metadata.get('title', item.chunk.document_id)}"
        )
    if context.related_documents:
        lines.append("- related documents via graph: " + ", ".join(context.related_documents))
    return lines


def get_structured_answer(question: str, document_payloads: list[dict[str, str]]) -> str | None:
    lowered = question.lower()
    if not document_payloads:
        return None
    lines: list[str] = []
    signature_mode = any(key in lowered for key in ["quién firm", "quien firm", "aprob", "elabor", "firmante"])
    structured_mode = any(key in lowered for key in ["fecha", "instituci", "presupuesto", "plazo", "garant", "proyecto"])
    for payload in document_payloads:
        title = payload.get("title", "documento")
        try:
            signatures = json.loads(payload.get("signatures") or "{}")
        except Exception:
            signatures = {}
        try:
            structured_fields = json.loads(payload.get("structured_fields") or "{}")
        except Exception:
            structured_fields = {}
        if signature_mode:
            for role, name in signatures.items():
                lines.append(f"- {title}: {role} -> {name}")
        if structured_mode and not signature_mode:
            for key, value in structured_fields.items():
                lines.append(f"- {title}: {key} -> {value}")
    if not lines:
        return None
    if signature_mode:
        return "Firmas o roles detectados:\n" + "\n".join(lines)
    return "Datos estructurados detectados:\n" + "\n".join(lines)


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
    if is_signature_question(question):
        signature_lines: list[str] = []
        for entity in retrieved.entities:
            if entity.entity_type != "unknown":
                signature_lines.append(f"- {entity.name} ({entity.entity_type})")
            else:
                signature_lines.append(f"- {entity.name}")
        if signature_lines:
            return "Firmas o roles detectados:\n" + "\n".join(signature_lines)
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
