from pathlib import Path
import os

from dotenv import load_dotenv

# Load environment variables from repo root and backend/.env (if present).
REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = "sqlite:///./hackathon_todo.db"
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]
