from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass

from .extract import extract_entities, is_signature_question, normalize_for_matching
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
    return {
        token.lower().strip(".,;:()[]{}")
        for token in query.split()
        if token.strip() and token.lower().strip(".,;:()[]{}") not in GENERAL_QUERY_WORDS
    }


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


def _is_broad_question(query: str) -> bool:
    lowered = query.lower()
    broad_markers = ["qué trata", "de qué trata", "what is it", "about", "resumen", "summary"]
    return len(_query_tokens(query)) <= 2 or any(marker in lowered for marker in broad_markers)


def retrieve(
    query: str,
    graph_store: GraphStore,
    vector_store: VectorStore,
    limit: int = 3,
    document_id: str | None = None,
    allowed_document_ids: set[str] | None = None,
    document_metadata: dict[str, dict[str, str]] | None = None,
    embedding_model: str | None = None,
) -> list[RetrievedChunk]:
    def _is_allowed(candidate_document_id: str | None) -> bool:
        if candidate_document_id is None:
            return False
        if document_id and candidate_document_id != document_id:
            return False
        if allowed_document_ids is not None and candidate_document_id not in allowed_document_ids:
            return False
        return True

    vector_candidates = vector_store.search(query, limit=max(limit, 5), embedding_model=embedding_model)
    vector_candidates = [candidate for candidate in vector_candidates if _is_allowed(candidate[0].document_id)]

    relevant_entities = [
        entity
        for entity in graph_store.list_entities()
        if entity.document_id and _is_allowed(entity.document_id) and _entity_hit_score(query, entity.name) > 0
    ]
    relevant_document_ids = {entity.document_id for entity in relevant_entities}

    graph_chunks = graph_store.list_chunks()
    if document_id:
        graph_chunks = [chunk for chunk in graph_chunks if chunk.document_id == document_id]
    if allowed_document_ids is not None:
        graph_chunks = [chunk for chunk in graph_chunks if chunk.document_id in allowed_document_ids]
    elif relevant_document_ids:
        graph_chunks = [chunk for chunk in graph_chunks if chunk.document_id in relevant_document_ids]

    scored: dict[str, RetrievedChunk] = {}
    weights = _question_type_weights(query)
    broad_question = _is_broad_question(query)
    for chunk, score in vector_candidates:
        metadata = document_metadata.get(chunk.document_id, {}) if document_metadata else {}
        recency_boost = _document_recency_score(metadata)
        overlap = _token_overlap_score(query, chunk.text)
        graph_signal = 1.0 if relevant_document_ids and chunk.document_id in relevant_document_ids else 0.0
        irrelevance_penalty = weights["penalty"] if overlap == 0 else max(0.0, weights["penalty"] - overlap)
        if broad_question:
            irrelevance_penalty += 0.15
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
        if broad_question:
            irrelevance_penalty += 0.1
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
    for chunk in graph_store.list_chunks():
        if not _is_allowed(chunk.document_id):
            continue
        fallback.append(RetrievedChunk(chunk=chunk, score=0.0, origin="fallback"))
        if len(fallback) >= limit:
            break
    return fallback


def retrieve_context(
    query: str,
    graph_store: GraphStore,
    vector_store: VectorStore,
    limit: int = 3,
    document_id: str | None = None,
    allowed_document_ids: set[str] | None = None,
    document_metadata: dict[str, dict[str, str]] | None = None,
    embedding_model: str | None = None,
) -> RetrievedContext:
    retrieved_chunks = retrieve(
        query,
        graph_store,
        vector_store,
        limit=limit,
        document_id=document_id,
        allowed_document_ids=allowed_document_ids,
        document_metadata=document_metadata,
        embedding_model=embedding_model,
    )
    entities = extract_entities([item.chunk for item in retrieved_chunks])
    graph_entities = graph_store.list_entities()
    if allowed_document_ids is not None:
        graph_entities = [entity for entity in graph_entities if entity.document_id in allowed_document_ids]
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
                    if allowed_document_ids is None or entity.document_id in allowed_document_ids:
                        related_documents.append(entity.document_id)
                if entity.id == relation.target_id:
                    if allowed_document_ids is None or entity.document_id in allowed_document_ids:
                        related_documents.append(entity.document_id)
    related_documents = [
        doc
        for doc in dict.fromkeys(related_documents)
        if doc not in retrieved_document_ids and (allowed_document_ids is None or doc in allowed_document_ids)
    ]
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
    if not document_payloads:
        return None
    normalized_question = normalize_for_matching(question)
    lines: list[str] = []
    signature_mode = any(
        key in normalized_question
        for key in [
            "quien firm",
            "quienes firm",
            "quien firma",
            "quienes firman",
            "firmante",
            "firmas",
            "suscrib",
            "aprobo",
            "aprob",
            "elaboro",
            "elabor",
        ]
    )
    structured_mode = any(
        key in normalized_question
        for key in ["fecha", "instituci", "presupuesto", "plazo", "garant", "proyecto"]
    )
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


def _normalize_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split()).strip()


def _truncate_text(text: str, max_chars: int = 180) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "..."


def _first_sentence(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""
    match = re.match(r"^(.+?[.!?])(?:\s|$)", normalized)
    if match:
        return _truncate_text(match.group(1))
    return _truncate_text(normalized)


def _build_short_answer(question: str, retrieved: RetrievedContext) -> str:
    top_chunk = retrieved.chunks[0] if retrieved.chunks else None
    if top_chunk:
        summary_source = _first_sentence(top_chunk.chunk.text) or _truncate_text(top_chunk.chunk.text)
        if top_chunk.chunk.metadata.get("title"):
            evidence_source = (
                f"{top_chunk.chunk.metadata['title']} · "
                f"{top_chunk.chunk.document_id}#{top_chunk.chunk.index} "
                f"(score={top_chunk.score:.2f})"
            )
        else:
            evidence_source = f"{top_chunk.chunk.document_id}#{top_chunk.chunk.index} (score={top_chunk.score:.2f})"
        benefit_source = "Aclara el contenido principal del fragmento recuperado."
    else:
        summary_source = "No encontré contexto suficiente en los documentos cargados."
        benefit_source = "No puedo inferir un beneficio concreto sin fragmentos relevantes."
        evidence_source = "0 fragmentos recuperados."
    return "\n".join(
        [
            f"Resumen: {_truncate_text(summary_source, 180)}",
            f"Beneficio: {_truncate_text(benefit_source, 180)}",
            f"Evidencia: {_truncate_text(evidence_source, 180)}",
        ]
    )


def _format_model_answer(answer: str, retrieved: RetrievedContext, question: str) -> str:
    normalized = _normalize_text(answer)
    if not normalized:
        return _build_short_answer(question, retrieved)
    if normalized.startswith("{") or "```" in normalized:
        return _build_short_answer(question, retrieved)

    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    if len(lines) != 3:
        return _build_short_answer(question, retrieved)

    labels = {"resumen": None, "beneficio": None, "evidencia": None}
    for line in lines:
        lower = line.lower()
        for label in labels:
            prefix = f"{label}:"
            if lower.startswith(prefix):
                labels[label] = line.split(":", 1)[1].strip()
                break

    if any(value is None for value in labels.values()):
        return _build_short_answer(question, retrieved)

    return "\n".join(
        [
            f"Resumen: {_truncate_text(labels['resumen'], 180)}",
            f"Beneficio: {_truncate_text(labels['beneficio'], 180)}",
            f"Evidencia: {_truncate_text(labels['evidencia'], 180)}",
        ]
    )


def _word_count(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def _requested_word_count(question: str) -> int | None:
    normalized = _normalize_text(question).lower()
    patterns = [
        r"\b(\d{2,4})\s*(?:palabras?|words?)\b",
        r"\b(?:informe|reporte|resumen)\s+de\s+(\d{2,4})\s*(?:palabras?|words?)\b",
        r"\b(?:con|en)\s+(\d{2,4})\s*(?:palabras?|words?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            requested = int(match.group(1))
            if requested > 0:
                return requested
    return None


def _question_requests_long_form(question: str) -> bool:
    normalized = _normalize_text(question).lower()
    if _requested_word_count(question) is not None:
        return True
    long_markers = (
        "informe",
        "reporte",
        "detall",
        "explic",
        "analiz",
        "desarroll",
        "redact",
        "ampli",
        "profund",
        "extens",
        "resumen ejecutivo",
    )
    return any(marker in normalized for marker in long_markers)


def _infer_answer_mode(question: str, answer_length: str = "auto", target_words: int | None = None) -> tuple[str, int | None]:
    requested_words = target_words if target_words and target_words > 0 else _requested_word_count(question)
    if answer_length == "short":
        return "short", None
    if answer_length == "long":
        return "long", requested_words
    if requested_words is not None:
        return "long", requested_words
    if _question_requests_long_form(question):
        return "long", requested_words
    return "short", None


def _lowercase_initial(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return normalized
    return normalized[0].lower() + normalized[1:]


def _long_answer_reference(item: RetrievedChunk) -> str:
    title = item.chunk.metadata.get("title")
    base = f"{item.chunk.document_id}#{item.chunk.index} (score={item.score:.2f})"
    if title:
        return f"{title} · {base}"
    return base


def _build_long_answer(question: str, retrieved: RetrievedContext, target_words: int | None = None) -> str:
    chunks = retrieved.chunks[:5]
    if not chunks:
        return "\n\n".join(
            [
                "Resumen ejecutivo: No encontre fragmentos relevantes en el contexto recuperado.",
                "Desarrollo: Sin evidencia util, no es posible ampliar la respuesta sin inventar datos.",
                "Conclusion: Carga mas documentos o ajusta la consulta para obtener un informe mas preciso.",
            ]
        )

    paragraphs: list[str] = []
    primary_chunk = chunks[0]
    primary_text = _first_sentence(primary_chunk.chunk.text) or _truncate_text(primary_chunk.chunk.text, 240)
    primary_text = primary_text.rstrip(".")
    if primary_text:
        paragraphs.append(
            "Resumen ejecutivo: "
            f"La consulta apunta principalmente a {_lowercase_initial(primary_text)}. "
            f"El fragmento mas relevante proviene de {_long_answer_reference(primary_chunk)}."
        )

    details: list[str] = []
    for item in chunks:
        snippet = _first_sentence(item.chunk.text) or _truncate_text(item.chunk.text, 220)
        snippet = snippet.rstrip(".")
        details.append(f"{_long_answer_reference(item)} aporta que {_lowercase_initial(snippet)}")
    if details:
        paragraphs.append("Desarrollo: " + " ".join(details) + ".")

    if retrieved.entities:
        entity_details = []
        for entity in retrieved.entities[:8]:
            if entity.entity_type != "unknown":
                entity_details.append(f"{entity.name} ({entity.entity_type})")
            else:
                entity_details.append(entity.name)
        paragraphs.append(
            "Entidades y relaciones: el contexto menciona "
            + ", ".join(entity_details)
            + ". Estas referencias ayudan a ubicar actores, sistemas o conceptos clave dentro del corpus."
        )

    if target_words:
        length_hint = f"Se pidio aproximarse a {target_words} palabras."
    else:
        length_hint = "La respuesta se redacto como informe sintetico con foco en claridad y trazabilidad."
    paragraphs.append(
        "Conclusion: "
        + length_hint
        + " La salida debe servir como lectura ejecutiva y como punto de partida para profundizar con otra consulta."
    )
    return "\n\n".join(paragraphs)


def _format_long_model_answer(
    answer: str,
    retrieved: RetrievedContext,
    question: str,
    target_words: int | None = None,
) -> str:
    normalized = _normalize_text(answer)
    if not normalized:
        return _build_long_answer(question, retrieved, target_words)
    if normalized.startswith("{") or "```" in normalized:
        return _build_long_answer(question, retrieved, target_words)
    minimum_words = max(90, int(target_words * 0.55) if target_words else 130)
    if _word_count(normalized) < minimum_words:
        return _build_long_answer(question, retrieved, target_words)
    return normalized


def compose_answer(
    question: str,
    retrieved: RetrievedContext,
    model_name: str | None = None,
    answer_length: str = "auto",
    target_words: int | None = None,
) -> str:
    mode, inferred_target_words = _infer_answer_mode(question, answer_length=answer_length, target_words=target_words)
    if is_signature_question(question):
        signature_lines: list[str] = []
        for entity in retrieved.entities:
            if entity.entity_type != "unknown":
                signature_lines.append(f"- {entity.name} ({entity.entity_type})")
            else:
                signature_lines.append(f"- {entity.name}")
        if signature_lines:
            return "Firmas o roles detectados:\n" + "\n".join(signature_lines)
        return "No pude identificar firmantes claros en el contexto recuperado."
    context_lines = [f"- [{item.score:.2f}] {_truncate_text(item.chunk.text, 160)}" for item in retrieved.chunks[:6]]
    entity_lines = [f"- {entity.name} ({entity.entity_type})" for entity in retrieved.entities[:10]]
    if mode == "long":
        if enabled(OpenRouterConfig()) and model_name:
            try:
                max_tokens = None
                if inferred_target_words:
                    max_tokens = max(256, int(inferred_target_words * 1.8))
                else:
                    max_tokens = 900
                prompt = [
                    {
                        "role": "system",
                        "content": (
                            "Responde siempre en espanol. Redacta una respuesta bien estructurada, clara y natural. "
                            "Si el usuario pide un informe, responde con 3 a 5 parrafos y evita JSON, tablas o bloques de codigo. "
                            "Usa solo el contexto proporcionado, no inventes informacion y conserva un tono profesional. "
                            "Si se indico un numero de palabras, aproximante a ese objetivo sin sacrificar claridad."
                        ),
                    },
                    {
                        "role": "user",
                        "content": "Pregunta:\n"
                        + question
                        + (
                            f"\n\nObjetivo de longitud:\nAproximadamente {inferred_target_words} palabras."
                            if inferred_target_words
                            else "\n\nObjetivo de longitud:\nRedacta un informe extenso y bien redactado."
                        )
                        + "\n\nContexto:\n"
                        + "\n".join(context_lines)
                        + ("\n\nEntidades:\n" + "\n".join(entity_lines) if entity_lines else ""),
                    },
                ]
                answer = openrouter_chat(prompt, model=model_name, max_tokens=max_tokens)
                if looks_english(answer):
                    answer = translate_to_spanish(answer, model_name=model_name)
                return _format_long_model_answer(answer, retrieved, question, target_words=inferred_target_words)
            except Exception:
                pass
        return _build_long_answer(question, retrieved, inferred_target_words)
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
            return _format_model_answer(answer, retrieved, question)
        except Exception:
            pass
    return _build_short_answer(question, retrieved)
GENERAL_QUERY_WORDS = {
    "que",
    "qué",
    "cual",
    "cuál",
    "quien",
    "quién",
    "quienes",
    "quiénes",
    "es",
    "son",
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "documento",
    "documentos",
    "proyecto",
    "proyectos",
}
