"""Shared settings for QSLRM."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

  database_url: str = "postgresql+psycopg://qslrm:qslrm@localhost:5432/qslrm"
  mvp_drug_class: str = "kinase_inhibitor"
  model_version: str = "qslrm-v1.0.0"

  faers_max_per_drug: int = 100
  faers_page_size: int = 100
  chembl_activity_limit: int = 200
  http_timeout_s: float = 60.0
  http_max_retries: int = 3
  raw_data_dir: str = "data/raw"
  processed_data_dir: str = "data/processed"
  action_fused_threshold: float = 60.0
  rising_velocity_threshold: float = 0.5
  allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

  def cors_origins(self) -> list[str]:
    return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
  return Settings()
