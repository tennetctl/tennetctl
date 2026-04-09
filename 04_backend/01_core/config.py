"""Process-level config — only DATABASE_URL and TENNETCTL_ENV come from env.

Everything else is read from "00_schema_migrations"."10_fct_settings" at
startup. See 03_docs/features/00_setup/04_architecture/01_architecture.md.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(
        ...,
        alias="DATABASE_URL",
        description="Write-role Postgres DSN. The only credential the app reads from env.",
    )
    tennetctl_env: str = Field(
        default="dev",
        alias="TENNETCTL_ENV",
        description="Deployment environment. Used only for first-install seeding.",
    )
    allowed_origins: str = Field(
        default="http://localhost:53000,http://127.0.0.1:53000,http://localhost:3000,http://127.0.0.1:3000",
        alias="ALLOWED_ORIGINS",
        description="Comma-separated list of origins allowed by CORS.",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
