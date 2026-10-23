from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    jwt_secret: str = "change-me"
    database_url: str = "postgresql+asyncpg://devmind:devmind@localhost:5432/devmind"
    redis_url: str = "redis://localhost:6379/0"
    default_chat_provider: str = "mock"
    default_embedding_provider: str = "local"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    sandbox_timeout_seconds: int = 8
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


settings = Settings()
