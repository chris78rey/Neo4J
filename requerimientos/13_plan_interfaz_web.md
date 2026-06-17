# Plan de interfaz web para GraphRAG

## Objetivo
Construir una interfaz web para:
- subir archivos,
- lanzar ingestión,
- hacer preguntas,
- ver contexto recuperado,
- inspeccionar entidades y relaciones detectadas,
- monitorear el estado del procesamiento.

## Arquitectura propuesta

### Frontend
- React o Next.js
- UI simple para carga de archivos y chat
- panel de documentos y jobs
- panel de contexto recuperado

### Backend
- FastAPI como API principal
- endpoints para documentos, preguntas y estado
- validación con Pydantic

### Procesamiento
- reutilizar `neo4j_graphrag`
- mantener la lógica de ingestión y consulta fuera del frontend
- ejecutar ingestión como job asíncrono

### Persistencia
- Neo4j para el grafo
- Qdrant para vectores
- almacenamiento temporal de archivos cargados

### Jobs
- usar Redis + RQ o Celery si la cola crece
- para MVP simple, background tasks de FastAPI pueden servir

## Flujo funcional
1. El usuario sube un archivo.
2. La API crea un job de ingestión.
3. El motor procesa texto, chunks, embeddings y grafo.
4. La UI consulta el estado del job.
5. El usuario hace una pregunta.
6. La API recupera contexto y devuelve respuesta con entidades.

## Priorización
1. API mínima.
2. UI mínima.
3. Ingestión asíncrona.
4. Consultas con historial.
5. Mejora visual y monitoreo.
