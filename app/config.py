import json

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://genewizard:genewizard@localhost:5432/genewizard"
    max_upload_size: int = 5 * 1024 * 1024 * 1024  # 5GB
    max_decompressed_size: int = 10 * 1024 * 1024 * 1024  # 10GB
    cors_origins_raw: str = "http://localhost:3000,https://genewizard.net,https://www.genewizard.net"
    environment: str = "development"  # development | production

    # Clerk
    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = "https://api.clerk.com/v1/jwks"

    # Feature flags
    prs_enabled: bool = True

    # Rate limiting
    upload_rate_limit: int = 10  # per user per hour

    # Temp file directory for uploads
    temp_dir: str = "/tmp/genewizard"

    model_config = {"env_prefix": "", "case_sensitive": False, "env_file": ".env", "extra": "ignore"}

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS_RAW as comma-separated string or JSON array."""
        raw = self.cors_origins_raw
        if raw.startswith("["):
            return json.loads(raw)
        return [o.strip() for o in raw.split(",") if o.strip()]

    @model_validator(mode="after")
    def normalize_database_url(self):
        """Railway provides postgres:// but asyncpg needs postgresql+asyncpg://"""
        url = self.database_url
        if self.environment == "production" and "localhost" in url:
            raise ValueError("DATABASE_URL must be set in production (not localhost default)")
        if url.startswith("postgres://"):
            self.database_url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            self.database_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self


settings = Settings()
