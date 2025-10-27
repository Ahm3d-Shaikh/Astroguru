from motor.motor_asyncio import AsyncIOMotorClient
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus  # <-- important

class Settings(BaseSettings):
    MONGO_USERNAME: str
    MONGO_PASSWORD: str
    MONGO_HOST: str
    MONGO_DB: str
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )

@lru_cache()
def get_settings():
    return Settings()

_settings = get_settings()

# URL-encode username and password
username = quote_plus(_settings.MONGO_USERNAME)
password = quote_plus(_settings.MONGO_PASSWORD)

MONGO_URI = f"mongodb+srv://{username}:{password}@{_settings.MONGO_HOST}/{_settings.MONGO_DB}?retryWrites=true&w=majority"

# Create async Mongo client
_client = AsyncIOMotorClient(MONGO_URI)
db = _client[_settings.MONGO_DB]
