"""
Конфигурация Normalizer API — Pydantic Settings
"""
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
    server_port: int = 8200

    # n8n webhook URLs
    n8n_base_url: str = "http://localhost:5678"
    n8n_classify_url: str = "/webhook/normalizer/classify"
    n8n_extract_brand_models_url: str = "/webhook/normalizer/extract-brand-models"
    n8n_validate_brand_url: str = "/webhook/normalizer/validate-brand"
    n8n_validate_models_url: str = "/webhook/normalizer/validate-models"

    # AI thresholds
    confidence_threshold: float = 0.8  # ниже → на модерацию

    # HTTP client
    http_timeout: int = 60

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = {"env_prefix": "NORMALIZER_"}


settings = Settings()
