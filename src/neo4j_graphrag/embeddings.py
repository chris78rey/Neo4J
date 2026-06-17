from __future__ import annotations

from .models import Chunk


def build_embeddings(chunks: list[Chunk], model_name: str) -> list[list[float]]:
    _ = model_name
    embeddings: list[list[float]] = []
    for chunk in chunks:
        base = float(sum(ord(char) for char in chunk.text) % 1000)
        embeddings.append([base, base / 10.0, base / 100.0])
    return embeddings
