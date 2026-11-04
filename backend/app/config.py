from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./orchestra.db"
    GROQ_API_KEY: str = ""
    GROQ_INTENT_MODEL: str = "meta-llama/llama-3.3-70b-versatile"
    GROQ_EVIDENCE_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_MODE: str = "sandbox"
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    MEDIA_DIR: str = "media"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
