from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    id: str
    path: str
    title: str
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    index: int
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Entity:
    id: str
    document_id: str
    name: str
    entity_type: str = "unknown"


@dataclass(frozen=True)
class Relation:
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = 1.0
