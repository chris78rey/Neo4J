# Plan de aprovechamiento de grafos y embeddings

Checklist para ir ejecutando de forma incremental. La idea es no desaprovechar lo que ya existe en el proyecto y convertirlo en un flujo híbrido de recuperación y respuesta.

## 1. Validación de ingesta

- [x] Persistir cada documento en el store de grafos.
- [x] Persistir cada documento en el store de embeddings/vector.
- [x] Validar que el número de chunks guardados coincida con el número esperado.
- [x] Fallar la ingesta si el grafo o el vector store no guardan todo.
- [x] Guardar fecha de ingesta.
- [x] Guardar hora de Ecuador UTC-5.
- [x] Guardar metadata de firmas y roles del documento.

## 2. Recuperación híbrida

- [x] Recuperar chunks por embeddings como primera señal.
- [x] Expandir contexto por vecinos en el grafo.
- [x] Re-ranquear resultados mezclando similitud vectorial y señal de grafo.
- [x] Penalizar resultados sin relación con la pregunta.
- [x] Priorizar documentos más recientes cuando el usuario lo pida.

## 3. Consulta por tipo de pregunta

- [x] Detectar preguntas sobre firmas, autores y aprobación.
- [x] Responder firmas y roles desde metadata estructurada.
- [x] Detectar preguntas sobre fechas, presupuesto, actores y fases.
- [x] Responder preguntas estructuradas desde metadata antes que desde LLM.
- [x] Detectar preguntas de alcance amplio vs puntual.

## 4. Explotación del grafo

- [x] Crear nodos semánticos para actores, fases, presupuesto y requisitos.
- [x] Conectar documentos con entidades clave y relaciones útiles.
- [x] Permitir expansión de contexto por entidades relacionadas.
- [x] Permitir navegación por documento -> entidad -> relación -> otro documento.
- [x] Exponer en UI qué nodos y relaciones entraron al contexto.

## 5. Mejora del ranking

- [x] Introducir score combinado: embedding + grafo + recencia.
- [ ] Ajustar pesos por tipo de pregunta.
- [x] Dar preferencia a firmas, actores y secciones estructuradas cuando aplique.
- [x] Evitar que una coincidencia semántica dé una respuesta fuera de contexto.
- [x] Distinguir qué resultado vino de embeddings, grafo o fallback.

## 6. UX de usuario

- [x] Mostrar documentos cargados con fecha de ingesta.
- [x] Mostrar alcance activo de `Ask`: all, latest, last_n.
- [x] Mostrar resumen del contexto usado.
- [x] Mostrar por qué se eligieron los documentos recuperados.
- [x] Mantener una vista clara para texto pegado, archivo o ruta.

## 7. Observabilidad

- [x] Registrar cuántos chunks vinieron por embeddings.
- [x] Registrar cuántos chunks vinieron por expansión del grafo.
- [x] Registrar cuándo se usó metadata estructurada en vez del LLM.
- [x] Registrar fallos de validación de ingesta.
- [x] Mostrar estado del último job con detalle legible.

## 8. Criterio de cierre

- [x] Una pregunta sobre firma responde desde metadata estructurada.
- [x] Una pregunta sobre contenido general mezcla embeddings y grafo.
- [x] Una pregunta sobre últimos documentos respeta recencia.
- [x] La UI muestra claramente qué corpus se usó.
- [x] La ingesta falla si no se persiste en ambos stores.
