# Graph Report - Neo4J  (2026-06-17)

## Corpus Check
- 53 files · ~10,810 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 382 nodes · 817 edges · 38 communities (33 shown, 5 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 140 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `03dfd750`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]

## God Nodes (most connected - your core abstractions)
1. `Document` - 34 edges
2. `Chunk` - 34 edges
3. `GraphStore` - 31 edges
4. `Entity` - 30 edges
5. `InMemoryGraphStore` - 30 edges
6. `Relation` - 25 edges
7. `VectorStore` - 25 edges
8. `InMemoryVectorStore` - 24 edges
9. `ask_question()` - 20 edges
10. `Neo4jGraphStore` - 20 edges

## Surprising Connections (you probably didn't know these)
- `test_signature_question_detection()` --calls--> `is_signature_question()`  [EXTRACTED]
  tests/test_extract.py → src/neo4j_graphrag/extract.py
- `test_pipeline_ingest_roundtrip()` --calls--> `Pipeline`  [EXTRACTED]
  tests/test_pipeline.py → src/neo4j_graphrag/connectors.py
- `test_retrieve_context_filters_to_document()` --calls--> `ingest_document()`  [EXTRACTED]
  tests/test_retrieval.py → src/neo4j_graphrag/connectors.py
- `test_retrieve_prefers_most_recent_document_when_scores_tie()` --calls--> `ingest_document()`  [EXTRACTED]
  tests/test_retrieval.py → src/neo4j_graphrag/connectors.py
- `test_retrieve_returns_relevant_chunk()` --calls--> `ingest_document()`  [EXTRACTED]
  tests/test_retrieval.py → src/neo4j_graphrag/connectors.py

## Import Cycles
- None detected.

## Communities (38 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (15): GraphRAG completo desde el inicio con embeddings, LLM y grafo conectado, Neo4j Community + Qdrant + LLM externo + scripts Python/Go para construir GraphRAG, Bajo consumo: pocos documentos, chunks pequeños, embeddings por lotes y consultas controladas, GraphRAG completo desde el inicio con embeddings, LLM y grafo conectado, GraphRAG funcional: documentos, embeddings, LLM, búsqueda vectorial y relaciones en Neo4j, GraphRAG funcional: documentos, embeddings, LLM, búsqueda vectorial y relaciones en Neo4j, Documentos iniciales: PDF, Word o TXT de un solo tema, Flujo de procesamiento: carga directa documento->texto->chunks->embeddings->Qdrant->relaciones básicas Neo4j (+7 more)

### Community 1 - "Community 1"
Cohesion: 0.18
Nodes (24): ingest_document(), Pipeline, PipelineResult, extract_entities(), extract_relations(), extract_semantic_entities(), extract_signatures(), extract_structured_fields() (+16 more)

### Community 2 - "Community 2"
Cohesion: 0.57
Nodes (8): Use external embeddings via OpenRouter with >1000 dimensions and controlled cost, 10_modelo_embeddings.md (Embeddings Model Requirement), 11_control_costos_ia.md (Cost Control Requirement), Use LLM only for questions, important entity extraction, and relevant relationship generation, Economic model as primary, better model as fallback for hard questions, embeddings separately, 12_estrategia_modelos.md (Model Strategy Requirement), prtpreguntas.md (Original Requirements Document), README.md (Requirements Index)

### Community 3 - "Community 3"
Cohesion: 0.38
Nodes (7): Proceso de carga directa, Modelo simple de grafo, Función de LLM para responder preguntas, Modelo LLM económico chino, Neo4j, OpenRouter, Qdrant

### Community 21 - "Community 21"
Cohesion: 0.16
Nodes (25): BackgroundTasks, BaseModel, ask_question(), AskResponse, current_ingest_timestamp(), DeleteResponse, DocumentResponse, documents_metadata_by_id() (+17 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (4): FileJobStore, JobStore, MemoryJobStore, test_file_job_store_roundtrip()

### Community 23 - "Community 23"
Cohesion: 0.29
Nodes (6): Backend, Estado, Frontend, Neo4j GraphRAG, OpenRouter, Uso

### Community 25 - "Community 25"
Cohesion: 0.18
Nodes (10): Arquitectura propuesta, Backend, Flujo funcional, Frontend, Jobs, Objetivo, Persistencia, Plan de interfaz web para GraphRAG (+2 more)

### Community 26 - "Community 26"
Cohesion: 0.07
Nodes (7): GraphStore, Neo4jGraphStore, QdrantVectorStore, Chunk, Document, Entity, Relation

### Community 27 - "Community 27"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+10 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (18): 1. Frontend web, 2. API backend, 3. Motor GraphRAG, 4. Cola de trabajo, 5. Almacenamiento, Arquitectura de interfaz web para GraphRAG, Backend, Componentes (+10 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (18): dependencies, react, react-dom, react-router-dom, devDependencies, @types/react, @types/react-dom, typescript (+10 more)

### Community 31 - "Community 31"
Cohesion: 0.14
Nodes (3): AppContext, DocumentRecord, Job

### Community 33 - "Community 33"
Cohesion: 0.19
Nodes (25): Any, build_embeddings(), is_signature_question(), chat(), embeddings(), enabled(), OpenRouterConfig, _request() (+17 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (30): ArgumentParser, Namespace, delete_document(), health(), build_parser(), cmd_ask(), cmd_doctor(), cmd_ingest() (+22 more)

### Community 35 - "Community 35"
Cohesion: 0.20
Nodes (9): 1. Validación de ingesta, 2. Recuperación híbrida, 3. Consulta por tipo de pregunta, 4. Explotación del grafo, 5. Mejora del ranking, 6. UX de usuario, 7. Observabilidad, 8. Criterio de cierre (+1 more)

## Knowledge Gaps
- **87 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+82 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Document` connect `Community 21` to `Community 1`, `Community 34`, `Community 26`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `get_job_store()` connect `Community 21` to `Community 34`, `Community 22`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `InMemoryGraphStore` connect `Community 34` to `Community 1`, `Community 26`, `Community 21`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `Document` (e.g. with `BackgroundTasks` and `AskResponse`) actually correct?**
  _`Document` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `Chunk` (e.g. with `Pipeline` and `PipelineResult`) actually correct?**
  _`Chunk` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `GraphStore` (e.g. with `Pipeline` and `PipelineResult`) actually correct?**
  _`GraphStore` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `Entity` (e.g. with `Pipeline` and `PipelineResult`) actually correct?**
  _`Entity` has 23 INFERRED edges - model-reasoned connections that need verification._