Respecto al flujo de procesamiento de documentos, ¿qué proceso debe construirse primero?
a) Carga directa: documento → texto → chunks → embeddings → Qdrant → relaciones básicas en Neo4j. (RECOMENDADA)

Respecto al modelo inicial del grafo en Neo4j, ¿qué estructura debe usarse?
a) Modelo simple: Documento, Chunk, Tema, Entidad y Relación. (RECOMENDADA)

Respecto al uso del LLM externo, ¿qué función debe cumplir al inicio?
a) Responder preguntas usando contexto recuperado desde Qdrant y relaciones básicas desde Neo4j. (RECOMENDADA)

Debe usarse con openrouter lo que sea necesario procesar que requiere llm o embedings si spon necesarios modelos chinos baratos en ekl cao de llm y puede ser de embedings modelos de mas de 1000 dimensiones que no son tan caros
