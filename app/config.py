"""Баптаулар. Мәндер .env файлынан (немесе орта айнымалыларынан) оқылады."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> None:
    """Өте қарапайым .env оқығыш: KEY=VALUE. Орта айнымалысы бар болса, оны өзгертпейді."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> dict:
    _load_env(ROOT / ".env")
    env = os.environ.get
    return {
        "SECRET_KEY": env("SECRET_KEY", ""),
        "DATABASE_URL": env("DATABASE_URL", f"sqlite:///{ROOT / 'warehouse.db'}"),
        "TOKEN_HOURS": int(env("TOKEN_HOURS", "8")),
        "COOKIE_SECURE": env("COOKIE_SECURE", "0") == "1",
        "ADMIN_USERNAME": env("ADMIN_USERNAME", ""),
        "ADMIN_EMAIL": env("ADMIN_EMAIL", "admin@example.com"),
        "ADMIN_PASSWORD": env("ADMIN_PASSWORD", ""),
        "MANAGER_USERNAME": env("MANAGER_USERNAME", ""),
        "MANAGER_EMAIL": env("MANAGER_EMAIL", "manager@example.com"),
        "MANAGER_PASSWORD": env("MANAGER_PASSWORD", ""),
        "SEED_DEMO_DATA": env("SEED_DEMO_DATA", "0") == "1",
        "LOG_FILE": env("LOG_FILE", str(ROOT / "logs" / "app.log")),
        "LOG_LEVEL": env("LOG_LEVEL", "INFO"),
    }
