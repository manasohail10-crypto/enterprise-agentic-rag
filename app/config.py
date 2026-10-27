from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str
    GROQ_API_KEY: str
    GROQ_FALLBACK_API_KEY: str | None = None
    QDRANT_API_KEY: str
    QDRANT_CLUSTER_ENDPOINT: str
    PORTKEY_API_KEY: str
    PORTKEY_PRIMARY_CONFIG_ID: str
    JINA_API_KEY: str | None = None
    LOGFIRE_TOKEN: str | None = None
    POSTGRES_URI: str | None = None
    API_KEY: str | None = None
    RATE_LIMIT_PER_MINUTE: int = 20
    STRICT_STARTUP: bool = False

    TAVILY_API_KEY: str | None = None
    WEB_SEARCH_ENABLED: bool = True
    TAVILY_MAX_RESULTS: int = 3
    RERANK_MIN_SCORE: float = 0.22

    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    PROMPT_LABEL: str = "production"

    QDRANT_COLLECTION: str = "enterprise_rag"
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"


setting = Setting()