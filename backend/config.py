from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    razorpay_key_id: str
    razorpay_key_secret: str
    anthropic_api_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

