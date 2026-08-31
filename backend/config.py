from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    razorpay_key_id: str
    razorpay_key_secret: str
    razorpay_webhook_secret: str = "razorgate_webhook_secret_dev"
    anthropic_api_key: Optional[str] = None
    claude_api_key: Optional[str] = None
    claude_base_url: Optional[str] = None
    claude_model: Optional[str] = None
    llm_provider: str = "claude"

    @property
    def api_key(self) -> str:
        return self.claude_api_key or self.anthropic_api_key or ""

    @property
    def base_url(self) -> Optional[str]:
        return self.claude_base_url or None

    @property
    def model_name(self) -> str:
        return self.claude_model or "claude-3-5-sonnet-20001022"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
