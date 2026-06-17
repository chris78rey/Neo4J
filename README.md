# Neo4j GraphRAG

Scaffold inicial para un GraphRAG con Neo4j, Qdrant y LLM externo.

## Estado

- CLI básica para ingestión de documentos de texto.
- Configuración por variables de entorno.
- Modelo mínimo para documentos, chunks, entidades y relaciones.
- Backend FastAPI con API, jobs persistidos y UI integrada.
- Frontend separado en `frontend/` con Vite + React.
- OpenRouter para chat y embeddings por configuración.

## Uso

```bash
python -m neo4j_graphrag.cli ingest path/to/document.txt
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Backend

```bash
python -m uvicorn neo4j_graphrag.api:app --reload
```

## OpenRouter

```bash
export OPENROUTER_API_KEY="..."
export OPENROUTER_CHAT_MODEL="openai/gpt-4o-mini"
export OPENROUTER_EMBEDDING_MODEL="..."
```
