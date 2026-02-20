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

    # Cookie fetching settings
    cookie_fetch_concurrency: int = 2   # max parallel Playwright sessions
    cookie_max_age_hours: int = 6        # TTL for cached cookies
    cookie_fetch_limit: int = 20         # max proxies per refresh cycle
    cookie_fetch_timeout: int = 120      # Playwright subprocess timeout (seconds)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
