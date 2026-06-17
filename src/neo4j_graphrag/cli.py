import argparse

from .config import load_config
from .connectors import ingest_document
from .ingest import build_chunks, load_document
from .retrieval import compose_answer, retrieve_context
from .store import build_graph_store_from_config, build_vector_store_from_config


def cmd_ingest(args: argparse.Namespace) -> int:
    config = load_config()
    document = load_document(args.path)
    chunks = build_chunks(document, config.chunk_size, config.chunk_overlap)
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    ingest_document(
        document=document,
        chunks=chunks,
        graph_store=graph_store,
        vector_store=vector_store,
        model_name=config.embedding_model,
    )
    print(f"document={document.title} chunks={len(chunks)}")
    for chunk in chunks:
        print(f"- chunk {chunk.index}: {len(chunk.text)} chars")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    config = load_config()
    document = load_document(args.path)
    chunks = build_chunks(document, config.chunk_size, config.chunk_overlap)
    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    ingest_document(
        document=document,
        chunks=chunks,
        graph_store=graph_store,
        vector_store=vector_store,
        model_name=config.embedding_model,
    )
    retrieved = retrieve_context(args.question, graph_store, vector_store, limit=args.limit)
    print(compose_answer(args.question, retrieved))
    close = getattr(graph_store, "close", None)
    if callable(close):
        close()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    _ = args
    config = load_config()
    checks = [
        ("NEO4J_URI", config.neo4j_uri),
        ("NEO4J_USER", config.neo4j_user),
        ("NEO4J_PASSWORD", "***" if config.neo4j_password else ""),
        ("QDRANT_URL", config.qdrant_url),
        ("QDRANT_COLLECTION", config.qdrant_collection),
        ("EMBEDDING_MODEL", config.embedding_model),
    ]
    print("Config:")
    for key, value in checks:
        print(f"- {key}={value}")

    graph_store = build_graph_store_from_config(config)
    vector_store = build_vector_store_from_config(config)
    print("Backends:")
    print(f"- graph_store={graph_store.__class__.__name__}")
    print(f"- vector_store={vector_store.__class__.__name__}")
    try:
        graph_ok = graph_store.healthcheck()
    except Exception:
        graph_ok = False
    try:
        vector_ok = vector_store.healthcheck()
    except Exception:
        vector_ok = False
    print("Health:")
    print(f"- graph_store={'OK' if graph_ok else 'FAIL'}")
    print(f"- vector_store={'OK' if vector_ok else 'FAIL'}")
    if graph_ok:
        try:
            print(f"- graph_probe={graph_store.probe()}")
        except Exception as exc:
            print(f"- graph_probe=FAIL ({exc.__class__.__name__})")
    if vector_ok:
        try:
            print(f"- vector_probe={vector_store.probe()}")
        except Exception as exc:
            print(f"- vector_probe=FAIL ({exc.__class__.__name__})")

    close = getattr(graph_store, "close", None)
    if callable(close):
        close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neo4j-graphrag")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Load a document and split it into chunks")
    ingest.add_argument("path", type=str, help="Path to a .txt or .md document")
    ingest.set_defaults(func=cmd_ingest)

    ask = subparsers.add_parser("ask", help="Ask a question against a local document")
    ask.add_argument("path", type=str, help="Path to a .txt or .md document")
    ask.add_argument("question", type=str, help="Question to ask about the document")
    ask.add_argument("--limit", type=int, default=3, help="Maximum number of chunks to retrieve")
    ask.set_defaults(func=cmd_ask)

    doctor = subparsers.add_parser("doctor", help="Check configuration and backend availability")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
