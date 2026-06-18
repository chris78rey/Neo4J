from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic import Field

from .config import load_config
from .connectors import ingest_document
from .extract import is_signature_question, is_structured_question
from .job_store import get_job_store
from .ingest import build_chunks, load_document
from .models import Document
from .retrieval import compose_answer, explain_retrieval, get_structured_answer, retrieve_context
from .store import build_graph_store_from_config, build_vector_store_from_config, get_graph_store_status, get_vector_store_status


app = FastAPI(title="Neo4j GraphRAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def update_job(job_store, job_id: str, status: str, detail: str) -> None:
    job_store.set(job_id, {"status": status, "detail": detail})


def normalize_document_id(document_id: str) -> str:
    return document_id.removeprefix("doc:")


def current_ingest_timestamp() -> tuple[str, str]:
    utc_now = datetime.now(timezone.utc)
    ecuador_tz = timezone(timedelta(hours=-5))
    return utc_now.isoformat(), utc_now.astimezone(ecuador_tz).isoformat()


class QuestionRequest(BaseModel):
    question: str
    limit: int = 3
    model: str | None = None
    embedding_model: str | None = None
    answer_length: Literal["auto", "short", "long"] = "auto"
    target_words: int | None = Field(default=None, ge=10, le=4000)


class IngestResponse(BaseModel):
    job_id: str
    document_id: str
    document_title: str
    chunks: int
    entities: int
    relations: int


class AskResponse(BaseModel):
    answer: str
    document_count: int
    chunk_count: int
    duration_ms: int = 0
    explanation: list[str] = Field(default_factory=list)
    embedding_chunk_count: int = 0
    graph_chunk_count: int = 0
    related_documents: list[str] = Field(default_factory=list)
    structured_answer_used: bool = False


class JobResponse(BaseModel):
    job_id: str
    status: str
    detail: str | None = None


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    source: str
    source_type: str | None = None
    ingested_at_utc: str | None = None
    ingested_at_ecuador: str | None = None
    signatures: dict[str, str] | None = None
    structured_fields: dict[str, str] | None = None
    job_id: str | None = None
    chunks: int | None = None
    entities: int | None = None
    relations: int | None = None


class DeleteResponse(BaseModel):
    document_id: str
    status: str


def sort_documents_by_ingest(payloads: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        payloads,
        key=lambda item: item.get("ingested_at_utc") or item.get("ingested_at_ecuador") or "",
    )


def documents_metadata_by_id(payloads: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for payload in payloads:
        document_id = payload.get("document_id")
        if not document_id:
            continue
        metadata[document_id] = payload
    return metadata


def filter_documents_by_path(payloads: list[dict[str, str]], path: str | None) -> list[dict[str, str]]:
    if not path:
        return payloads
    normalized_path = path.strip()
    return [
        payload
        for payload in payloads
        if payload.get("source") == normalized_path
        or payload.get("document_id") == normalized_path
        or payload.get("title") == normalized_path
    ]


@app.get("/health")
def health() -> dict[str, str]:
    config = load_config()
    job_store = get_job_store(config.job_store_path)
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    status = {
        "api": "ok",
        "graph_store": "ok" if graph_store.healthcheck() else "fail",
        "vector_store": "ok" if vector_store.healthcheck() else "fail",
        "graph_store_mode": get_graph_store_status(),
        "vector_store_mode": get_vector_store_status(),
        "graph_store_backend": graph_store.__class__.__name__,
        "vector_store_backend": vector_store.__class__.__name__,
        "jobs": "ok" if isinstance(job_store.list(), dict) else "fail",
    }
    return status


@app.post("/documents", response_model=IngestResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    path: str | None = Form(None),
    text: str | None = Form(None),
    title: str | None = Form(None),
    embedding_model: str | None = Form(None),
) -> IngestResponse:
    config = load_config()
    job_store = get_job_store(config.job_store_path)
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    job_id = str(uuid4())
    update_job(job_store, job_id, "running", "queued")

    if file is not None:
        uploaded_name = Path(file.filename or "document.txt").name
        with NamedTemporaryFile(delete=False, suffix=Path(file.filename or "document.txt").suffix or ".txt") as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name
        document = replace(
            load_document(temp_path),
            path=uploaded_name,
            title=Path(uploaded_name).stem,
        )
    elif path:
        document = load_document(path)
    elif text:
        document = Document(
            id=str(uuid4()),
            path=title or "inline-text",
            title=title or "inline-text",
            text=text,
        )
    else:
        raise ValueError("file, path or text is required")
    ingested_at_utc, ingested_at_ecuador = current_ingest_timestamp()
    model_name = embedding_model or config.openrouter_embedding_model or config.embedding_model

    def run_ingest() -> None:
        try:
            update_job(job_store, job_id, "running", "loading document")
            chunks = build_chunks(document, config.chunk_size, config.chunk_overlap)
            update_job(job_store, job_id, "running", f"chunking {len(chunks)} chunks")
            update_job(job_store, job_id, "running", "building embeddings and graph")
            result = ingest_document(
                document=document,
                chunks=chunks,
                graph_store=graph_store,
                vector_store=vector_store,
                model_name=model_name,
            )
            enriched_document = result.document
            job_store.set(
                f"doc:{document.id}",
                {
                    "document_id": enriched_document.id,
                    "title": enriched_document.title,
                    "source": enriched_document.path,
                    "source_type": "text" if text else ("path" if path else "file"),
                    "text": enriched_document.text,
                    "signatures": json.dumps(enriched_document.metadata.get("signatures", {}), ensure_ascii=False),
                    "structured_fields": json.dumps(enriched_document.metadata.get("structured_fields", {}), ensure_ascii=False),
                    "ingested_at_utc": ingested_at_utc,
                    "ingested_at_ecuador": ingested_at_ecuador,
                    "job_id": job_id,
                    "chunks": str(len(result.chunks)),
                    "entities": str(len(result.entities)),
                    "relations": str(len(result.relations)),
                },
            )
            update_job(
                job_store,
                job_id,
                "completed",
                f"chunks={len(result.chunks)} entities={len(result.entities)} relations={len(result.relations)}",
            )
        except Exception as exc:
            update_job(job_store, job_id, "failed", f"{exc.__class__.__name__}: {exc}")

    background_tasks.add_task(run_ingest)

    return IngestResponse(
        job_id=job_id,
        document_id=document.id,
        document_title=document.title,
        chunks=0,
        entities=0,
        relations=0,
    )


@app.get("/documents", response_model=dict[str, dict[str, str]])
def list_documents() -> dict[str, dict[str, str]]:
    config = load_config()
    return get_job_store(config.job_store_path).list_by_prefix("doc:")


@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str) -> DocumentResponse:
    config = load_config()
    normalized_id = normalize_document_id(document_id)
    payload = get_job_store(config.job_store_path).get(f"doc:{normalized_id}")
    if payload is None:
        return DocumentResponse(document_id=normalized_id, title="unknown", source="unknown")
    return DocumentResponse(
        document_id=normalized_id,
        title=payload.get("title", "unknown"),
        source=payload.get("source", "unknown"),
        source_type=payload.get("source_type"),
        ingested_at_utc=payload.get("ingested_at_utc"),
        ingested_at_ecuador=payload.get("ingested_at_ecuador"),
        signatures=json.loads(payload["signatures"]) if payload.get("signatures") else None,
        structured_fields=json.loads(payload["structured_fields"]) if payload.get("structured_fields") else None,
        job_id=payload.get("job_id"),
        chunks=int(payload.get("chunks", "0")) if payload.get("chunks") else None,
        entities=int(payload.get("entities", "0")) if payload.get("entities") else None,
        relations=int(payload.get("relations", "0")) if payload.get("relations") else None,
    )


@app.delete("/documents/{document_id}", response_model=DeleteResponse)
def delete_document(document_id: str) -> DeleteResponse:
    config = load_config()
    job_store = get_job_store(config.job_store_path)
    normalized_id = normalize_document_id(document_id)
    payload = job_store.get(f"doc:{normalized_id}")
    if payload is None:
        return DeleteResponse(document_id=normalized_id, status="not_found")
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    graph_store.delete_document(normalized_id)
    delete_vector = getattr(vector_store, "delete_document", None)
    if callable(delete_vector):
        delete_vector(normalized_id)
    job_store.delete(f"doc:{normalized_id}")
    return DeleteResponse(document_id=normalized_id, status="deleted")


@app.post("/questions", response_model=AskResponse)
def ask_question(
    request: QuestionRequest,
    path: str | None = Query(None),
    scope: str = Query("all"),
    latest_count: int = Query(5, ge=1, le=50),
) -> AskResponse:
    config = load_config()
    started_at = datetime.now(timezone.utc)
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    embedding_model_value = request.embedding_model or config.openrouter_embedding_model or config.embedding_model
    chat_model = request.model or config.openrouter_chat_model or config.llm_model
    job_store = get_job_store(config.job_store_path)
    docs = list(job_store.list_by_prefix("doc:").values())
    docs = filter_documents_by_path(docs, path)
    if path and not docs:
        return AskResponse(
            answer=f"No persisted document matched path={path!r}. Ingest the document first.",
            document_count=len(job_store.list_by_prefix("doc:")),
            chunk_count=0,
            duration_ms=int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
            explanation=[],
            embedding_chunk_count=0,
            graph_chunk_count=0,
            related_documents=[],
            structured_answer_used=False,
        )
    corpus = docs
    if scope == "latest":
        corpus = sort_documents_by_ingest(corpus)[-1:]
    elif scope == "last_n":
        corpus = sort_documents_by_ingest(corpus)[-latest_count:]
    if is_structured_question(request.question) or is_signature_question(request.question):
        structured_answer = get_structured_answer(request.question, corpus)
        if structured_answer:
            return AskResponse(
                answer=structured_answer,
                document_count=len(corpus),
                chunk_count=0,
                duration_ms=int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
                explanation=[],
                embedding_chunk_count=0,
                graph_chunk_count=0,
                related_documents=[],
                structured_answer_used=True,
            )
    allowed_document_ids = {payload["document_id"] for payload in corpus if payload.get("document_id")}
    context = retrieve_context(
        request.question,
        graph_store,
        vector_store,
        limit=request.limit,
        embedding_model=embedding_model_value,
        allowed_document_ids=allowed_document_ids or None,
        document_metadata=documents_metadata_by_id(corpus),
    )
    answer = compose_answer(
        request.question,
        context,
        model_name=chat_model,
        answer_length=request.answer_length,
        target_words=request.target_words,
    )
    explanation = explain_retrieval(context)
    embedding_chunk_count = sum(1 for item in context.chunks if item.origin == "embeddings+graph")
    graph_chunk_count = sum(1 for item in context.chunks if item.origin == "graph")
    return AskResponse(
        answer=answer,
        document_count=len(job_store.list_by_prefix("doc:")),
        chunk_count=len(context.chunks),
        duration_ms=int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
        explanation=explanation,
        embedding_chunk_count=embedding_chunk_count,
        graph_chunk_count=graph_chunk_count,
        related_documents=context.related_documents or [],
        structured_answer_used=False,
    )


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    config = load_config()
    payload = get_job_store(config.job_store_path).get(job_id)
    if payload is None:
        return JobResponse(job_id=job_id, status="unknown", detail="job not found")
    return JobResponse(job_id=job_id, status=payload["status"], detail=payload.get("detail"))


@app.get("/jobs")
def list_jobs() -> dict[str, dict[str, str]]:
    config = load_config()
    return get_job_store(config.job_store_path).list()
