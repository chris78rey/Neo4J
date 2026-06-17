from pathlib import Path
from uuid import uuid4

from .models import Chunk, Document


SUPPORTED_EXTENSIONS = {".txt", ".md"}


def load_document(path: str) -> Document:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    return Document(
        id=str(uuid4()),
        path=str(file_path),
        title=file_path.stem,
        text=text,
        metadata={},
    )


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks


def build_chunks(document: Document, chunk_size: int, overlap: int) -> list[Chunk]:
    parts = chunk_text(document.text, chunk_size, overlap)
    return [
        Chunk(
            id=f"{document.id}:{index}",
            document_id=document.id,
            index=index,
            text=part,
            metadata={"path": document.path, "title": document.title},
        )
        for index, part in enumerate(parts)
    ]
