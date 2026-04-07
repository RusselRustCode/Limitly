from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import timedelta
class Settings(BaseSettings):
    """
    Класс для загрузки конфигурации из переменных окружения.
    Pydantic автоматически ищет переменные с соответствующими именами.
    """
    
    # Конфигурация MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_NAME: str = "LimithyDB"

    # Настройки для FastAPI
    API_V1_STR: str = "/v1"
    PROJECT_NAME: str = "Limithy"
    
    # Модель для указания файла .env
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE: timedelta = timedelta(minutes=30)

    # API ключ RusGPT
    RUSGPT_API_KEY: str

settings = Settings()