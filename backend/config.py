from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str = "razorgate_webhook_secret_dev"
    anthropic_api_key: Optional[str] = None
    claude_api_key: Optional[str] = None

    @property
    def api_key(self) -> str:
        return self.claude_api_key or self.anthropic_api_key or ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
