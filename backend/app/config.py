from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_BUCKET: str = "rag-blobs"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"

    JWT_SECRET: str = "change-me-to-32-plus-bytes-random-string"
    JWT_EXP_MIN: int = 60
    REFRESH_EXP_DAYS: int = 14

    # Local-first LLM: Ollama llama3.1:8b-instruct-q4_K_M (model id 46e0c10c039e)
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "llama3.1:8b-instruct-q4_K_M"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    TOP_K: int = 8

    # Chunking (Plan 03): fixed|recursive|semantic|proposition|layout
    CHUNK_STRATEGY: str = "recursive"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    # Embeddings (local Ollama, free): nomic-embed-text = 768d
    EMBED_MODEL: str = "nomic-embed-text"
    EMBED_DIM: int = 768

    # Retrieval
    RERANK_TOP_N: int = 5
    RERANK_ENABLED: bool = True
    ABSTAIN_TEXT: str = "I don't know based on the knowledge base."


settings = Settings()
