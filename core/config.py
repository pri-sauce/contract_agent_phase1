"""
config.py — Loads all settings from .env
Single source of truth for configuration across the entire agent.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Models
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "llama3.2:3b")
    FAST_MODEL: str = os.getenv("FAST_MODEL", "llama3.2:3b")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / os.getenv("DATA_DIR", "data")
    UPLOADS_DIR: Path = BASE_DIR / os.getenv("UPLOADS_DIR", "data/uploads")
    PROCESSED_DIR: Path = BASE_DIR / os.getenv("PROCESSED_DIR", "data/processed")
    KNOWLEDGE_BASE_DIR: Path = BASE_DIR / os.getenv("KNOWLEDGE_BASE_DIR", "data/knowledge_base")
    PLAYBOOK_PATH: Path = BASE_DIR / os.getenv("PLAYBOOK_PATH", "data/knowledge_base/playbook.yaml")

    # Chunking
    MAX_CHUNK_TOKENS: int = int(os.getenv("MAX_CHUNK_TOKENS", 512))
    CHUNK_OVERLAP_TOKENS: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", 50))

    # Agent
    RISK_THRESHOLD: str = os.getenv("RISK_THRESHOLD", "MEDIUM")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Path = BASE_DIR / os.getenv("LOG_FILE", "data/agent.log")

    @classmethod
    def ensure_dirs(cls):
        """Create all required directories if they don't exist."""
        for d in [cls.DATA_DIR, cls.UPLOADS_DIR, cls.PROCESSED_DIR, cls.KNOWLEDGE_BASE_DIR]:
            d.mkdir(parents=True, exist_ok=True)


# Singleton instance
config = Config()
config.ensure_dirs()
