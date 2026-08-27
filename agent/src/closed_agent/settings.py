from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    internal_api_base_url: str = "http://admin-nginx"
    internal_token: str = "dev-internal-token-change-me"
    skip_billing: bool = True
    cors_origins: str = "http://admin.localhost"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "localpassword"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-10-21"
    sample_root: Path = Path(__file__).resolve().parents[2] / "samples" / "office"


settings = Settings()
