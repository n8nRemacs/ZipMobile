from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = "https://bkxpajeqrkutktmtmwui.supabase.co"
    supabase_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8090
    log_level: str = "info"

    # JWT
    jwt_secret: str = "change-me-to-a-random-secret-at-least-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 30

    # OTP
    otp_provider: str = "console"
    otp_length: int = 6
    otp_expire_minutes: int = 5
    otp_max_attempts: int = 5
    otp_max_codes_per_hour: int = 5

    # Internal API
    internal_secret: str = "change-me-internal-secret"

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_bot_username: str = "zipmobile_bot"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "https://avito.newlcd.ru"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
