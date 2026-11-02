from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_api_key: str = "change-this-key"
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    environment: str = 'local'
    google_api_key: str = ''
    gemini_chat_model: str = 'gemini-2.5-flash'
    gemini_embedding_model: str = 'gemini-embedding-001'
    embedding_dimension: int = 768
    milvus_uri: str = 'http://localhost:19530'
    milvus_collection: str = 'banking_knowledge_v1'
    qdrant_path: str = './data/qdrant'
    qdrant_collection: str = 'banking_knowledge_v1'
    app_api_key: str = ''
    max_upload_mb: int = 20
    chunk_size: int = 1200
    chunk_overlap: int = 180
    retrieval_top_k: int = 8
    log_level: str = 'INFO'

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
