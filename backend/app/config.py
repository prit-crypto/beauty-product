import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
load_dotenv(BASE_DIR / ".env")


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "rule").lower())
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
    # tried in order when the main model is busy or rate-limited
    gemini_fallback_models: list[str] = field(default_factory=lambda: _list("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite"))
    # Gemini "thinking" effort: low is ~3x faster with the same accuracy for this chat (benchmarked); "" = model default
    gemini_thinking: str = field(default_factory=lambda: os.getenv("GEMINI_THINKING", "low"))
    # true: the AI also re-words replies (more natural, ~2x slower). false: the AI only reads messages (faster).
    ai_rewrite: bool = field(default_factory=lambda: os.getenv("AI_REWRITE", "true").lower() in ("1", "true", "yes"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    ai_timeout_s: float = field(default_factory=lambda: float(os.getenv("AI_TIMEOUT_SECONDS", "12")))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", "drbeauty-demo"))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", str(DATA_DIR / "app.db")))
    # product photos: drop <product id>.jpg/.png/.webp here and it shows up on the site and in the chat
    product_images_dir: str = field(default_factory=lambda: os.getenv("PRODUCT_IMAGES_DIR", str(BASE_DIR.parent / "frontend" / "public" / "products")))
    cors_origins: list[str] = field(default_factory=lambda: _list("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"))


settings = Settings()
