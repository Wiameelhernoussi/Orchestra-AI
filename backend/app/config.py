from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./orchestra.db"
    GROQ_API_KEY: str = ""
    GROQ_INTENT_MODEL: str = "openai/gpt-oss-120b"
    GROQ_EVIDENCE_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_EVIDENCE_FALLBACK_MODEL: str = "openai/gpt-oss-20b"
    GROQ_COMPARE_MODEL: str = "openai/gpt-oss-20b"
    GROQ_REASONING_EFFORT: str = "low"
    GROQ_INTENT_MAX_COMPLETION_TOKENS: int = 1200
    GROQ_EVIDENCE_MAX_COMPLETION_TOKENS: int = 800
    GROQ_MAX_RETRIES: int = 2
    GROQ_MAX_RETRY_WAIT_SECONDS: int = 60
    DEMO_MODE: Literal["mock", "real"] = "real"
    DEMO_CLIENT_PAYPAL_EMAIL: str = ""
    DEMO_SEED_TOKEN: str = ""
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_MODE: str = "sandbox"
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    MEDIA_DIR: str = "media"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
