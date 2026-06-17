from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import load_config
from .connectors import ingest_document
from .job_store import get_job_store
from .ingest import build_chunks, load_document
from .models import Document
from .retrieval import compose_answer, retrieve_context
from .store import build_graph_store_from_config, build_vector_store_from_config


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


class QuestionRequest(BaseModel):
    question: str
    limit: int = 3
    model: str | None = None
    embedding_model: str | None = None


class IngestResponse(BaseModel):
    job_id: str
    document_title: str
    chunks: int
    entities: int
    relations: int


class AskResponse(BaseModel):
    answer: str
    document_count: int
    chunk_count: int


class JobResponse(BaseModel):
    job_id: str
    status: str
    detail: str | None = None


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    source: str
    job_id: str | None = None
    chunks: int | None = None
    entities: int | None = None
    relations: int | None = None


class DeleteResponse(BaseModel):
    document_id: str
    status: str


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
        "jobs": "ok" if isinstance(job_store.list(), dict) else "fail",
    }
    close = getattr(graph_store, "close", None)
    if callable(close):
        close()
    return status


@app.post("/documents", response_model=IngestResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    path: str | None = Form(None),
    embedding_model: str | None = Form(None),
) -> IngestResponse:
    config = load_config()
    job_store = get_job_store(config.job_store_path)
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    job_id = str(uuid4())
    update_job(job_store, job_id, "running", "queued")

    if file is not None:
        with NamedTemporaryFile(delete=False, suffix=Path(file.filename or "document.txt").suffix or ".txt") as tmp:
            tmp.write(await file.read())
            temp_path = tmp.name
        document = load_document(temp_path)
    elif path:
        document = load_document(path)
    else:
        raise ValueError("file or path is required")

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
                model_name=embedding_model,
            )
            job_store.set(
                f"doc:{document.id}",
                {
                    "document_id": document.id,
                    "title": document.title,
                    "source": document.path,
                    "text": document.text,
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
        finally:
            close = getattr(graph_store, "close", None)
            if callable(close):
                close()

    background_tasks.add_task(run_ingest)

    return IngestResponse(
        job_id=job_id,
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
    try:
        graph_store.delete_document(normalized_id)
        delete_vector = getattr(vector_store, "delete_document", None)
        if callable(delete_vector):
            delete_vector(normalized_id)
        job_store.delete(f"doc:{normalized_id}")
        return DeleteResponse(document_id=normalized_id, status="deleted")
    finally:
        close = getattr(graph_store, "close", None)
        if callable(close):
            close()


@app.post("/questions", response_model=AskResponse)
def ask_question(request: QuestionRequest, path: str | None = Query(None)) -> AskResponse:
    config = load_config()
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    embedding_model_value = request.embedding_model or config.openrouter_embedding_model or config.embedding_model
    chat_model = request.model or config.openrouter_chat_model or config.llm_model
    job_store = get_job_store(config.job_store_path)
    if path:
        document = load_document(path)
        chunks = build_chunks(document, config.chunk_size, config.chunk_overlap)
        ingest_document(
            document=document,
            chunks=chunks,
            graph_store=graph_store,
            vector_store=vector_store,
            model_name=embedding_model_value,
        )
    else:
        documents = job_store.list_by_prefix("doc:")
        for payload in documents.values():
            source = payload.get("source")
            text = payload.get("text")
            document_id = payload.get("document_id")
            if not source:
                continue
            if text and document_id:
                document = Document(
                    id=document_id,
                    path=source,
                    title=payload.get("title", Path(source).stem),
                    text=text,
                )
            else:
                document = load_document(source)
            chunks = build_chunks(document, config.chunk_size, config.chunk_overlap)
            ingest_document(
                document=document,
                chunks=chunks,
                graph_store=graph_store,
                vector_store=vector_store,
                model_name=embedding_model_value,
            )
    context = retrieve_context(request.question, graph_store, vector_store, limit=request.limit)
    answer = compose_answer(request.question, context, model_name=chat_model)
    close = getattr(graph_store, "close", None)
    if callable(close):
        close()
    return AskResponse(
        answer=answer,
        document_count=len(job_store.list_by_prefix("doc:")),
        chunk_count=len(context.chunks),
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
