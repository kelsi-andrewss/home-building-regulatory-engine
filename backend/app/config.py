from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    database_echo: bool = False
    admin_api_key: str | None = None
    anthropic_api_key: str | None = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
