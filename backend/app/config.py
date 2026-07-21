import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Local Model Configurations
    LLM_MODEL_NAME: str = "Qwen/Qwen2.5-72B-Instruct"
    USE_LOCAL_LLM: bool = True  # Set to True to load model locally via transformers
    HF_TOKEN: str = ""  # Hugging Face Access Token for Serverless Inference API
    
    # Local Tesseract Path (for Windows)
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    # Database Configurations
    CHROMA_DB_DIR: str = str(Path(__file__).parent.parent / "chroma_db")

    # Neo4j Knowledge Graph (AuraDB Cloud)
    NEO4J_ENABLED: bool = True
    NEO4J_URI: str = "neo4j+ssc://199b1763.databases.neo4j.io"
    NEO4J_USERNAME: str = "199b1763"
    NEO4J_PASSWORD: str = "JCO1NjQxFo4N0JA61itHTS22MwsO4ldD3bty6-McQ40"

    
    # Embeddings and Reranker
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANK_MODEL: str = "BAAI/bge-reranker-base"
    USE_LOCAL_EMBEDDINGS: bool = False  # True to use sentence-transformers locally, False to call API / mock
    
    # Vector DB Collection name
    CHROMA_COLLECTION: str = "industrial_knowledge"
    
    # Server configs
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
