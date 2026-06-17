from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    neo4j_uri: str = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek/deepseek-v4-pro")
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "800"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "120"))
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "graphrag_chunks")
    job_store_path: str = os.getenv("JOB_STORE_PATH", ".neo4j_graphrag_jobs.json")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_chat_model: str = os.getenv("OPENROUTER_CHAT_MODEL", "deepseek/deepseek-v4-pro")
    openrouter_embedding_model: str = os.getenv("OPENROUTER_EMBEDDING_MODEL", "")


def load_config() -> AppConfig:
    return AppConfig()
