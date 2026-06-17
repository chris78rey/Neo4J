# Arquitectura de interfaz web para GraphRAG

## Objetivo
Definir una interfaz operativa para carga de documentos, ingestión asíncrona y preguntas sobre el conocimiento construido.

## Componentes

### 1. Frontend web
- Framework: React o Next.js.
- Pantallas:
  - carga de documentos,
  - listado de documentos,
  - detalle de documento,
  - chat de preguntas,
  - estado de jobs,
  - vista de contexto recuperado.

### 2. API backend
- Framework: FastAPI.
- Responsabilidades:
  - recibir archivos,
  - crear jobs,
  - exponer estado de jobs,
  - procesar preguntas,
  - devolver contexto y entidades.

### 3. Motor GraphRAG
- Reutiliza `neo4j_graphrag`.
- Funciones:
  - extraer texto,
  - chunking,
  - embeddings,
  - persistencia en Neo4j y Qdrant,
  - recuperación híbrida,
  - composición de respuesta.

### 4. Cola de trabajo
- Opción simple: `FastAPI BackgroundTasks`.
- Opción robusta: `Redis + RQ` o `Celery`.
- Recomendación:
  - usar tareas en background para MVP,
  - migrar a cola dedicada si hay concurrencia.

### 5. Almacenamiento
- Neo4j: grafo semántico.
- Qdrant: vectores.
- Storage temporal: archivos cargados antes de procesarlos.

## Endpoints propuestos

### Documentos
- `POST /documents` subir archivo y crear job de ingestión.
- `GET /documents` listar documentos cargados.
- `GET /documents/{id}` obtener detalle y estado.

### Jobs
- `GET /jobs/{id}` consultar progreso y error.

### Preguntas
- `POST /questions` enviar pregunta sobre un documento o conjunto de documentos.
- `GET /questions/{id}` consultar respuesta almacenada, si aplica.

### Salud
- `GET /health` revisar API.
- `GET /health/graph` revisar Neo4j.
- `GET /health/vector` revisar Qdrant.

## Estructura de carpetas sugerida

### Backend
```text
app/
  api/
  services/
  workers/
  models/
  main.py
```

### Frontend
```text
web/
  src/
    components/
    pages/
    hooks/
    lib/
```

## Flujo
1. El usuario carga un archivo.
2. La API lo guarda temporalmente.
3. Se encola la ingestión.
4. El worker ejecuta el pipeline GraphRAG.
5. La UI consulta el estado.
6. El usuario pregunta.
7. La API recupera contexto y responde.

## Criterios de aceptación
- Un archivo puede cargarse desde la UI.
- La ingestión no bloquea la interfaz.
- Se puede consultar el estado del procesamiento.
- Se puede hacer una pregunta y obtener respuesta con contexto.
- Neo4j y Qdrant siguen siendo la fuente de verdad del motor.
