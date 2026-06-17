from .models import Chunk, Document, Entity, Relation


class GraphStore:
    def upsert_document(self, document: Document) -> None:
        raise NotImplementedError

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        raise NotImplementedError

    def list_chunks(self) -> list[Chunk]:
        raise NotImplementedError

    def list_entities(self) -> list[Entity]:
        raise NotImplementedError

    def list_relations(self) -> list[Relation]:
        raise NotImplementedError

    def count_document_chunks(self, document_id: str) -> int:
        raise NotImplementedError

    def upsert_entities(self, entities: list[Entity]) -> None:
        raise NotImplementedError

    def upsert_relations(self, relations: list[Relation]) -> None:
        raise NotImplementedError

    def delete_document(self, document_id: str) -> None:
        raise NotImplementedError

    def healthcheck(self) -> bool:
        raise NotImplementedError

    def probe(self) -> str:
        raise NotImplementedError


class VectorStore:
    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        raise NotImplementedError

    def search(self, query: str, limit: int = 3) -> list[tuple[Chunk, float]]:
        raise NotImplementedError

    def count_document_chunks(self, document_id: str) -> int:
        raise NotImplementedError

    def healthcheck(self) -> bool:
        raise NotImplementedError

    def probe(self) -> str:
        raise NotImplementedError


class InMemoryGraphStore(GraphStore):
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, Chunk] = {}
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []

    def upsert_document(self, document: Document) -> None:
        self.documents[document.id] = document

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self.chunks[chunk.id] = chunk

    def list_chunks(self) -> list[Chunk]:
        return list(self.chunks.values())

    def list_entities(self) -> list[Entity]:
        return list(self.entities.values())

    def list_relations(self) -> list[Relation]:
        return list(self.relations)

    def count_document_chunks(self, document_id: str) -> int:
        return sum(1 for chunk in self.chunks.values() if chunk.document_id == document_id)

    def upsert_entities(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.entities[entity.id] = entity

    def upsert_relations(self, relations: list[Relation]) -> None:
        self.relations.extend(relations)

    def delete_document(self, document_id: str) -> None:
        self.documents.pop(document_id, None)
        chunk_ids = [chunk_id for chunk_id, chunk in self.chunks.items() if chunk.document_id == document_id]
        for chunk_id in chunk_ids:
            self.chunks.pop(chunk_id, None)
        entity_ids = [entity_id for entity_id, entity in self.entities.items() if entity.document_id == document_id]
        for entity_id in entity_ids:
            self.entities.pop(entity_id, None)
        self.relations = [
            relation
            for relation in self.relations
            if relation.source_id not in entity_ids and relation.target_id not in entity_ids
        ]

    def healthcheck(self) -> bool:
        return True

    def probe(self) -> str:
        return "in-memory graph ok"


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self.records: list[tuple[Chunk, list[float]]] = []

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        self.records.extend(zip(chunks, embeddings, strict=True))

    def search(self, query: str, limit: int = 3) -> list[tuple[Chunk, float]]:
        query_tokens = {token.lower() for token in query.split()}
        scored: list[tuple[Chunk, float]] = []
        for chunk, _embedding in self.records:
            chunk_tokens = {token.lower() for token in chunk.text.split()}
            score = float(len(query_tokens & chunk_tokens))
            scored.append((chunk, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def count_document_chunks(self, document_id: str) -> int:
        return sum(1 for chunk, _embedding in self.records if chunk.document_id == document_id)

    def healthcheck(self) -> bool:
        return True

    def probe(self) -> str:
        return "in-memory vector ok"


def build_embeds_stub(chunks: list[Chunk]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for chunk in chunks:
        value = float(len(chunk.text))
        embeddings.append([value, value / 10.0, value / 100.0])
    return embeddings


class Neo4jGraphStore(GraphStore):
    def __init__(self, uri: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def healthcheck(self) -> bool:
        with self.driver.session() as session:
            record = session.run("RETURN 1 AS ok").single()
            return bool(record and record["ok"] == 1)

    def probe(self) -> str:
        probe_doc = Document(id="probe", path="probe", title="probe", text="probe")
        probe_chunk = Chunk(id="probe:0", document_id="probe", index=0, text="probe", metadata={"path": "probe", "title": "probe"})
        self.upsert_document(probe_doc)
        self.upsert_chunks([probe_chunk])
        with self.driver.session() as session:
            record = session.run(
                "MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c:Chunk) RETURN count(c) AS count",
                id="probe",
            ).single()
            count = int(record["count"]) if record else 0
        with self.driver.session() as session:
            session.run("MATCH (d:Document {id: 'probe'}) DETACH DELETE d")
        return f"neo4j probe chunks={count}"

    def upsert_document(self, document: Document) -> None:
        query = """
        MERGE (d:Document {id: $id})
        SET d.path = $path,
            d.title = $title,
            d.text = $text
        """
        with self.driver.session() as session:
            session.run(query, id=document.id, path=document.path, title=document.title, text=document.text)

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        query = """
        UNWIND $chunks AS chunk
        MERGE (c:Chunk {id: chunk.id})
        SET c.document_id = chunk.document_id,
            c.index = chunk.index,
            c.text = chunk.text,
            c.path = chunk.path,
            c.title = chunk.title
        WITH c, chunk
        MATCH (d:Document {id: chunk.document_id})
        MERGE (d)-[:HAS_CHUNK]->(c)
        """
        payload = [
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "index": chunk.index,
                "text": chunk.text,
                "path": chunk.metadata.get("path", ""),
                "title": chunk.metadata.get("title", ""),
            }
            for chunk in chunks
        ]
        with self.driver.session() as session:
            session.run(query, chunks=payload)

    def list_chunks(self) -> list[Chunk]:
        query = """
        MATCH (c:Chunk)
        RETURN c.id AS id, c.document_id AS document_id, c.index AS index, c.text AS text, c.path AS path, c.title AS title
        ORDER BY c.index
        """
        with self.driver.session() as session:
            records = session.run(query)
            chunks: list[Chunk] = []
            for record in records:
                chunks.append(
                    Chunk(
                        id=record["id"],
                        document_id=record["document_id"],
                        index=record["index"],
                        text=record["text"],
                        metadata={"path": record["path"], "title": record["title"]},
                    )
                )
            return chunks

    def list_entities(self) -> list[Entity]:
        query = """
        MATCH (e:Entity)
        RETURN e.id AS id, e.document_id AS document_id, e.name AS name, e.entity_type AS entity_type
        """
        with self.driver.session() as session:
            records = session.run(query)
            entities: list[Entity] = []
            for record in records:
                entities.append(
                    Entity(
                        id=record["id"],
                        document_id=record["document_id"],
                        name=record["name"],
                        entity_type=record["entity_type"] or "unknown",
                    )
                )
            return entities

    def list_relations(self) -> list[Relation]:
        query = """
        MATCH (source:Entity)-[r:RELATED_TO]->(target:Entity)
        RETURN source.id AS source_id, target.id AS target_id, r.type AS relation_type, r.confidence AS confidence
        """
        with self.driver.session() as session:
            records = session.run(query)
            relations: list[Relation] = []
            for record in records:
                relations.append(
                    Relation(
                        source_id=record["source_id"],
                        target_id=record["target_id"],
                        relation_type=record["relation_type"],
                        confidence=float(record["confidence"] or 1.0),
                    )
                )
            return relations

    def count_document_chunks(self, document_id: str) -> int:
        query = """
        MATCH (c:Chunk {document_id: $document_id})
        RETURN count(c) AS count
        """
        with self.driver.session() as session:
            record = session.run(query, document_id=document_id).single()
            return int(record["count"]) if record else 0

    def upsert_entities(self, entities: list[Entity]) -> None:
        query = """
        UNWIND $entities AS entity
        MERGE (e:Entity {id: entity.id})
        SET e.name = entity.name,
            e.entity_type = entity.entity_type,
            e.document_id = entity.document_id
        """
        payload = [
            {
                "id": entity.id,
                "document_id": entity.document_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
            }
            for entity in entities
        ]
        with self.driver.session() as session:
            session.run(query, entities=payload)

    def delete_document(self, document_id: str) -> None:
        with self.driver.session() as session:
            session.run(
                """
                MATCH (d:Document {id: $document_id})
                OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
                WITH d, collect(DISTINCT c) AS chunks
                OPTIONAL MATCH (e:Entity {document_id: $document_id})
                WITH d, chunks, collect(DISTINCT e) AS entities
                FOREACH (chunk IN chunks | DETACH DELETE chunk)
                FOREACH (entity IN entities | DETACH DELETE entity)
                DETACH DELETE d
                """,
                document_id=document_id,
            )

    def upsert_relations(self, relations: list[Relation]) -> None:
        query = """
        UNWIND $relations AS relation
        MATCH (source:Entity {id: relation.source_id})
        MATCH (target:Entity {id: relation.target_id})
        MERGE (source)-[r:RELATED_TO {type: relation.relation_type}]->(target)
        SET r.confidence = relation.confidence
        """
        payload = [
            {
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "relation_type": relation.relation_type,
                "confidence": relation.confidence,
            }
            for relation in relations
        ]
        with self.driver.session() as session:
            session.run(query, relations=payload)

    def delete_document(self, document_id: str) -> None:
        with self.driver.session() as session:
            session.run(
                """
                MATCH (d:Document {id: $document_id})
                DETACH DELETE d
                """,
                document_id=document_id,
            )


class QdrantVectorStore(VectorStore):
    def __init__(self, url: str, api_key: str, collection_name: str) -> None:
        from qdrant_client import QdrantClient

        self.client = QdrantClient(url=url, api_key=api_key or None)
        self.collection_name = collection_name

    def ensure_collection(self, vector_size: int) -> None:
        from qdrant_client.http import models as rest

        existing = {collection.name for collection in self.client.get_collections().collections}
        if self.collection_name in existing:
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=rest.VectorParams(size=vector_size, distance=rest.Distance.COSINE),
        )

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        self.ensure_collection(len(embeddings[0]))
        points = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            points.append(
                {
                    "id": chunk.id,
                    "vector": embedding,
                    "payload": {
                        "document_id": chunk.document_id,
                        "index": chunk.index,
                        "text": chunk.text,
                        "path": chunk.metadata.get("path", ""),
                        "title": chunk.metadata.get("title", ""),
                    },
                }
            )
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(self, query: str, limit: int = 3) -> list[tuple[Chunk, float]]:
        query_embedding = [float(len(query)), float(len(query)) / 10.0, float(len(query)) / 100.0]
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            with_payload=True,
        )
        matches: list[tuple[Chunk, float]] = []
        for result in results:
            payload = result.payload or {}
            matches.append(
                (
                    Chunk(
                        id=str(result.id),
                        document_id=str(payload.get("document_id", "")),
                        index=int(payload.get("index", 0)),
                        text=str(payload.get("text", "")),
                        metadata={
                            "path": str(payload.get("path", "")),
                            "title": str(payload.get("title", "")),
                        },
                    ),
                    float(result.score or 0.0),
                )
            )
        return matches

    def count_document_chunks(self, document_id: str) -> int:
        from qdrant_client.http import models as rest

        result = self.client.count(
            collection_name=self.collection_name,
            count_filter=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="document_id",
                        match=rest.MatchValue(value=document_id),
                    )
                ]
            ),
            exact=True,
        )
        return int(result.count)

    def healthcheck(self) -> bool:
        _ = self.client.get_collections()
        return True

    def delete_document(self, document_id: str) -> None:
        from qdrant_client.http import models as rest

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="document_id",
                            match=rest.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def probe(self) -> str:
        self.ensure_collection(3)
        return f"qdrant probe collection={self.collection_name}"


def build_graph_store_from_config(config) -> GraphStore:
    if config.neo4j_uri and config.neo4j_user and config.neo4j_password:
        try:
            return Neo4jGraphStore(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
        except Exception:
            pass
    return InMemoryGraphStore()


def build_vector_store_from_config(config) -> VectorStore:
    if config.qdrant_url:
        try:
            return QdrantVectorStore(config.qdrant_url, config.qdrant_api_key, config.qdrant_collection)
        except Exception:
            pass
    return InMemoryVectorStore()
