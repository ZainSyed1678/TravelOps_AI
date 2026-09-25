"""Application configuration module using Pydantic Settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "TravelOps AI"
    VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return []

    # PostgreSQL
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "travelops"
    POSTGRES_PASSWORD: str = "travelops_secure_password"
    POSTGRES_DB: str = "travelops"
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_CACHE_TTL_SECONDS: int = 3600

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Qdrant Vector Store
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_NAME: str = "travel_documents"
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # Neo4j Graph Database
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "travelops_neo4j_password"

    # Travel Provider APIs
    FLIGHT_PROVIDER: str = "mock"
    HOTEL_PROVIDER: str = "mock"
    BOOKING_PROVIDER: str = "mock"
    AMADEUS_CLIENT_ID: str = ""
    AMADEUS_CLIENT_SECRET: str = ""
    AMADEUS_ENVIRONMENT: str = "test"

    # LLM & AI Agents
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_NAME: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL_NAME: str = "claude-3-5-sonnet-20240620"

    # Observability
    METRICS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"

    # API Rate Limiting & Throttling
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    API_DOCS_ENABLED: bool = True


settings = Settings()
