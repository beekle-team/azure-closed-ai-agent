from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    internal_api_base_url: str = "http://admin-nginx"
    internal_token: str = "dev-internal-token-change-me"
    skip_billing: bool = True
    cors_origins: str = "http://admin.localhost"
    auth_mode: str = "local"
    agent_tokens: str = ""
    channel_webhook_secret: str = "local-webhook"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    rate_limit_per_minute: int = 60
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "localpassword"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-10-21"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"
    azure_storage_connection_string: str = ""
    azure_blob_container: str = "corpus"
    azure_ingest_queue: str = "ingest"
    azure_servicebus_connection_string: str = ""
    azure_servicebus_queue: str = "ingest"
    ingest_apply_inline: bool = True
    sample_root: Path = Path(__file__).resolve().parents[2] / "samples" / "office"
    mailpit_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 1025
    mail_from: str = "agent@localhost"
    graph_access_token: str = ""


settings = Settings()
