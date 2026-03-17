import os
from pathlib import Path


BACKEND_DIR = Path(__file__).absolute().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


_load_env_file(BACKEND_DIR / ".env")
_load_env_file(PROJECT_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "agenttrust-dev-secret")
    _database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(BACKEND_DIR / 'instance' / 'agenttrust.sqlite3').as_posix()}",
    )
    SQLALCHEMY_DATABASE_URI = _database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"pool_pre_ping": True, "pool_recycle": 300}
        if SQLALCHEMY_DATABASE_URI.startswith("postgresql://")
        else {}
    )
    PLATFORM_URL = os.getenv("PLATFORM_URL", "http://localhost:8000").rstrip("/")
    FRONTEND_APP_URL = os.getenv("FRONTEND_APP_URL", PLATFORM_URL).rstrip("/")
    FRONTEND_DIST_PATH = PROJECT_DIR / "frontend" / "dist"
    PLATFORM_SIGNING_KEY_PATH = Path(
        os.getenv(
            "PLATFORM_SIGNING_KEY_PATH",
            (BACKEND_DIR / "instance" / "platform_signing_key.pem").as_posix(),
        )
    )
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
    GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", f"{PLATFORM_URL}/api/v1/oauth/github/callback")
    X_CLIENT_ID = os.getenv("X_CLIENT_ID", "")
    X_CLIENT_SECRET = os.getenv("X_CLIENT_SECRET", "")
    X_REDIRECT_URI = os.getenv("X_REDIRECT_URI", f"{PLATFORM_URL}/api/v1/oauth/x/callback")
    MOLTBOOK_APP_KEY = os.getenv("MOLTBOOK_APP_KEY", "")
    MOLTBOOK_VERIFY_URL = os.getenv(
        "MOLTBOOK_VERIFY_URL",
        "https://moltbook.com/api/v1/agents/verify-identity",
    )
