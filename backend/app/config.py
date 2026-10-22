from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from the environment only.

    There is deliberately no default database URL: a missing setting must fail at
    startup, not connect with a guessed credential.
    """

    model_config = SettingsConfigDict(env_prefix="VITA_", env_file=".env", extra="ignore")

    database_url: str
    session_ttl_hours: int = 24 * 7
    # Private document storage root. Must live outside any web-served directory.
    storage_dir: str
    max_upload_bytes: int = 10 * 1024 * 1024
    # Optional. When unset, the verification assistant falls back to a deterministic,
    # rule-based draft instead of calling a model. Never required to run the app.
    llm_api_key: str | None = None
    llm_model: str = "nvidia/nemotron-3.5-lightning:free"  # NVIDIA Nemotron 3.5 Lightning on OpenRouter
    llm_provider: str = "openrouter"


settings = Settings()
