from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from the environment only.

    There is deliberately no default database URL: a missing setting must fail at
    startup, not connect with a guessed credential.
    """

    model_config = SettingsConfigDict(env_prefix="VITA_", env_file=".env", extra="ignore")

    database_url: str

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3_driver(cls, v: str) -> str:
        # Managed Postgres hosts (Render, Heroku, Railway, ...) hand out a bare
        # "postgresql://" connection string, which makes SQLAlchemy default to psycopg2 --
        # not installed here, this app uses psycopg3. Normalize it rather than requiring
        # every deploy target to know about the driver suffix.
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    session_ttl_hours: int = 24 * 7
    # Private document storage root. Must live outside any web-served directory.
    storage_dir: str
    max_upload_bytes: int = 10 * 1024 * 1024
    # Optional. When unset, the verification assistant falls back to a deterministic,
    # rule-based draft instead of calling a model. Never required to run the app.
    llm_api_key: str | None = None
    llm_model: str = "nvidia/nemotron-3.5-lightning:free"  # NVIDIA Nemotron 3.5 Lightning on OpenRouter
    llm_provider: str = "openrouter"
    # One-time bootstrap for the very first platform admin, for hosts with no DB/shell access
    # (e.g. Render's free tier). Unset by default -- the endpoint refuses every request until an
    # operator deliberately sets this in the host's environment, never through the app itself.
    admin_bootstrap_token: str | None = None


settings = Settings()
