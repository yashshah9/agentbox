"""Configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTBOX_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    default_timeout_seconds: int = 30
    max_output_bytes: int = 1_048_576
    sandbox_backend: str = "subprocess"  # subprocess | gvisor (future)
