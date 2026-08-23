"""
Configuration management for the Aster & Row support agent.
Loads settings from environment variables with sensible defaults.
Supports multiple LLM providers: OpenAI, Groq, and Google Gemini.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge-base"
DATA_DIR = PROJECT_ROOT / "data"
ORDERS_FILE = DATA_DIR / "orders.json"
CHROMA_PERSIST_DIR = PROJECT_ROOT / ".chroma_db"

# --- LLM Provider Configuration ---
# Supported providers: "openai", "groq", "gemini"
# Auto-detect from API key format if not specified
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()
API_KEY = os.getenv("OPENAI_API_KEY", "") or os.getenv("GROQ_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")

# Auto-detect provider from API key format
if not LLM_PROVIDER and API_KEY:
    if API_KEY.startswith("gsk_"):
        LLM_PROVIDER = "groq"
    elif API_KEY.startswith("AIza"):
        LLM_PROVIDER = "gemini"
    else:
        LLM_PROVIDER = "openai"

# Provider-specific defaults
PROVIDER_DEFAULTS = {
    "openai": {
        "base_url": None,  # Uses default OpenAI URL
        "model": "gpt-4o-mini",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-3.6-flash",
    },
}

# Get provider config (fall back to openai defaults)
_provider_config = PROVIDER_DEFAULTS.get(LLM_PROVIDER, PROVIDER_DEFAULTS["openai"])

# Final resolved settings
OPENAI_API_KEY = API_KEY
LLM_BASE_URL = os.getenv("LLM_BASE_URL", _provider_config["base_url"])
MODEL_NAME = os.getenv("MODEL_NAME", _provider_config["model"])

# Embedding model (only used if EMBEDDING_TYPE is "openai")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Embedding type: "local" (free, no API key) or "openai" (requires OpenAI API key)
EMBEDDING_TYPE = os.getenv("EMBEDDING_TYPE", "local")

# Retrieval
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
TOP_K = int(os.getenv("TOP_K", "7"))

# Debug
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Conversation
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "10"))
