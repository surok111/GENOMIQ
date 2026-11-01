"""Пути к SQLite, бэкапам и локальной базе знаний."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
GENEDB_DIR = DATA_DIR / "genedb"
DB_PATH = GENEDB_DIR / "genes.sqlite"
BACKUPS_DIR = DATA_DIR / "backups"
KB_CLEAN = DATA_DIR / "parsed_knowledge_base_clean.json"
KB_RAW = DATA_DIR / "parsed_knowledge_base.json"
ENV_FILE = ROOT / ".env"


def ensure_dirs() -> None:
    GENEDB_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def load_dotenv(path: Path | None = None) -> None:
    """Подхватывает KEY=VALUE из .env, не перезаписывая уже заданные переменные."""
    env_path = path or ENV_FILE
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
