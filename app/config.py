"""Runtime settings, read from environment variables (or a local .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    chat_model: str = os.getenv("CHAT_MODEL", "llama3.2:3b")
    embed_model: str = os.getenv("EMBED_MODEL", "nomic-embed-text")
    policies_dir: Path = Path(os.getenv("POLICIES_DIR", ROOT_DIR / "data" / "policies"))
    chroma_dir: Path = Path(os.getenv("CHROMA_DIR", ROOT_DIR / ".chroma"))
    collection: str = os.getenv("COLLECTION", "ledgerly_policies")
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "800"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "120"))
    top_k: int = int(os.getenv("TOP_K", "4"))
    # Cosine distance (0 = identical, 2 = opposite). Chunks further away than this
    # are treated as irrelevant; if none are left, the bot refuses instead of guessing.
    # Measured with nomic-embed-text: on-topic questions <= 0.45, off-topic >= 0.58.
    max_distance: float = float(os.getenv("MAX_DISTANCE", "0.50"))
    temperature: float = float(os.getenv("TEMPERATURE", "0"))
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "120"))
    # Input/context/output filters around the model (app/guardrails.py). On by default;
    # GUARDRAILS=off reproduces the unprotected baseline for red-team comparisons.
    guardrails: bool = os.getenv("GUARDRAILS", "on").lower() != "off"


settings = Settings()
