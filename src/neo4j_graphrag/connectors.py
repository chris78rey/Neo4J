from __future__ import annotations

from dataclasses import dataclass

from .embeddings import build_embeddings
from .extract import extract_entities, extract_relations, extract_semantic_entities, extract_signatures, extract_structured_fields
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
        signatures = extract_signatures(document.text)
        structured_fields = extract_structured_fields(document.text)
        document = Document(
            id=document.id,
            path=document.path,
            title=document.title,
            text=document.text,
            metadata={**document.metadata, "signatures": signatures, "structured_fields": structured_fields},
        )
        self.graph_store.upsert_document(document)
        self.graph_store.upsert_chunks(chunks)
        entities = extract_entities(chunks)
        semantic_entities = extract_semantic_entities(document.text, document.id)
        entities.extend(semantic_entities)
        relations = extract_relations(entities)
        anchor_entity = entities[0] if entities else None
        if anchor_entity:
            for semantic_entity in semantic_entities:
                relations.append(
                    Relation(
                        source_id=anchor_entity.id,
                        target_id=semantic_entity.id,
                        relation_type="HAS_SEMANTIC_FIELD",
                        confidence=1.0,
                        document_id=document.id,
                    )
                )
        if entities:
            self.graph_store.upsert_entities(entities)
        if relations:
            self.graph_store.upsert_relations(relations)
        self.vector_store.upsert_chunks(chunks, embeddings)
        expected_chunks = len(chunks)
        graph_chunks = self.graph_store.count_document_chunks(document.id)
        vector_chunks = self.vector_store.count_document_chunks(document.id)
        if graph_chunks != expected_chunks:
            raise RuntimeError(f"graph store chunk mismatch for {document.id}: expected {expected_chunks}, got {graph_chunks}")
        if vector_chunks != expected_chunks:
            raise RuntimeError(f"vector store chunk mismatch for {document.id}: expected {expected_chunks}, got {vector_chunks}")
        return PipelineResult(document=document, chunks=chunks, entities=entities, relations=relations)


def ingest_document(document: Document, chunks: list[Chunk], graph_store: GraphStore, vector_store: VectorStore, model_name: str) -> PipelineResult:
    embeddings = build_embeddings(chunks, model_name)
    pipeline = Pipeline(graph_store, vector_store)
    return pipeline.ingest(document, chunks, embeddings)
