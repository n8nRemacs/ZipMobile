"""
Конфигурация Profi Sandbox — Pydantic Settings
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "aws-1-eu-west-3.pooler.supabase.com"
    db_port: int = 5432
    db_user: str = "postgres.griexhozxrqtepcilfnu"
    db_password: str = "Mi31415926pSss!"
    db_name: str = "postgres"
    db_ssl: str = "require"
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Server
    server_port: int = 8100

    # Concurrency limits
    max_concurrent_downloads: int = 10
    max_concurrent_parsers: int = 5
    ai_batch_size: int = 50

    # HTTP client
    http_timeout: int = 60

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = {"env_prefix": "PROFI_"}


settings = Settings()
