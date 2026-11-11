"""CodeSentry — central settings (env-based, no secrets in code)."""
import os

class Settings:
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./codesentry.db")
    JWT_SECRET = os.environ.get("CODESENTRY_JWT_SECRET", "dev-only-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = 60 * 24 * 7
    GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID", "")
    GITHUB_APP_PRIVATE_KEY = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")
    GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # PAT fallback for demo posting
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "")
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq" if os.environ.get("GROQ_API_KEY") else "deterministic")
    EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "hash")
    REDIS_URL = os.environ.get("REDIS_URL", "")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", ""))
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    API_URL = os.environ.get("API_URL", "http://localhost:8000")
    ENV = os.environ.get("ENV", "development")
    # Review budgets (PRD §12)
    TOKEN_BUDGET_PER_SYMBOL = int(os.environ.get("TOKEN_BUDGET_PER_SYMBOL", "4000"))
    TOKEN_BUDGET_PER_PR = int(os.environ.get("TOKEN_BUDGET_PER_PR", "60000"))
    DEFAULT_CONFIDENCE_THRESHOLD = float(os.environ.get("DEFAULT_CONFIDENCE_THRESHOLD", "0.60"))
    MAX_PR_FILES = int(os.environ.get("MAX_PR_FILES", "200"))

settings = Settings()
