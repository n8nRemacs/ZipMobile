"""
Configuration via environment variables / .env file.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:Mi31415926pSss!@213.108.170.194:5433/postgres"
    host: str = "0.0.0.0"
    port: int = 8110
    log_level: str = "info"

    check_timeout: int = 10
    check_concurrency: int = 100

    daily_refresh_hour: int = 4
    daily_refresh_minute: int = 0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
