"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://canteenconnect-frontend.vercel.app",
    "https://canteen-student-portal.vercel.app",
    "https://canteen-admin-kappa.vercel.app",
    "https://canteen-admin-nine.vercel.app",
    "https://new-folder-app-three.vercel.app",
]


class Settings(BaseSettings):
    """Typed runtime configuration for the FastAPI service."""

    app_name: str = "Canteen Management SaaS API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    database_url: str = Field(default="sqlite:///./canteen.db", alias="DATABASE_URL")
    secret_key: str = Field(default="change-this-secret", alias="SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    auto_create_schema: bool = Field(default=False, alias="AUTO_CREATE_SCHEMA")
    initial_admin_username: str | None = Field(default=None, alias="INITIAL_ADMIN_USERNAME")
    initial_admin_email: str | None = Field(default=None, alias="INITIAL_ADMIN_EMAIL")
    initial_admin_password: str | None = Field(default=None, alias="INITIAL_ADMIN_PASSWORD")

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS),
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Parse comma-separated CORS origins from the environment."""

        def unique(origins: list[str]) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for origin in origins:
                normalized = origin.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
            return ordered

        if value is None or value == "":
            return list(DEFAULT_CORS_ORIGINS)
        if isinstance(value, str):
            return unique([*DEFAULT_CORS_ORIGINS, *value.split(",")])
        if isinstance(value, list):
            return unique([*DEFAULT_CORS_ORIGINS, *[str(origin) for origin in value]])
        raise ValueError("Invalid CORS origins configuration")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_value(cls, value: Any) -> bool:
        """Normalize permissive debug flag values from inherited env files."""

        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return False

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        raise ValueError("Invalid debug flag")

    @property
    def is_sqlite(self) -> bool:
        """Return whether the configured database is SQLite."""

        return self.database_url.startswith("sqlite")

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return a SQLAlchemy-compatible database URL."""

        if self.database_url.startswith("postgresql://") and "+psycopg" not in self.database_url:
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
