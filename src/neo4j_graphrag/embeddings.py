from __future__ import annotations

from .models import Chunk
from .openrouter import OpenRouterConfig, enabled, embeddings as openrouter_embeddings


def build_embeddings(chunks: list[Chunk], model_name: str) -> list[list[float]]:
    if enabled(OpenRouterConfig()) and model_name:
        try:
            return openrouter_embeddings([chunk.text for chunk in chunks], model=model_name)
        except Exception:
            pass
    embeddings: list[list[float]] = []
    for chunk in chunks:
        base = float(sum(ord(char) for char in chunk.text) % 1000)
        embeddings.append([base, base / 10.0, base / 100.0])
    return embeddings
