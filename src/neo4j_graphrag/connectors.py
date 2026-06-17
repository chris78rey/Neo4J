from __future__ import annotations

from dataclasses import dataclass

from .embeddings import build_embeddings
from .extract import extract_entities, extract_relations
from .models import Chunk, Document, Entity, Relation
from .store import GraphStore, VectorStore


@dataclass
class PipelineResult:
    document: Document
    chunks: list[Chunk]
    entities: list[Entity]
    relations: list[Relation]


class Pipeline:
    def __init__(self, graph_store: GraphStore, vector_store: VectorStore) -> None:
        self.graph_store = graph_store
        self.vector_store = vector_store

    def ingest(self, document: Document, chunks: list[Chunk], embeddings: list[list[float]]) -> PipelineResult:
        self.graph_store.upsert_document(document)
        self.graph_store.upsert_chunks(chunks)
        entities = extract_entities(chunks)
        relations = extract_relations(entities)
        if entities:
            self.graph_store.upsert_entities(entities)
        if relations:
            self.graph_store.upsert_relations(relations)
        self.vector_store.upsert_chunks(chunks, embeddings)
        return PipelineResult(document=document, chunks=chunks, entities=entities, relations=relations)


def ingest_document(document: Document, chunks: list[Chunk], graph_store: GraphStore, vector_store: VectorStore, model_name: str) -> PipelineResult:
    embeddings = build_embeddings(chunks, model_name)
    pipeline = Pipeline(graph_store, vector_store)
    return pipeline.ingest(document, chunks, embeddings)
