"""Снимки SQLite-базы генов и JSON базы знаний."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .paths import BACKUPS_DIR, DB_PATH, KB_CLEAN, KB_RAW, ensure_dirs
from .store import GeneStore

KEEP_LAST = 15


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_backups() -> list[dict]:
    ensure_dirs()
    items = []
    for d in sorted(BACKUPS_DIR.iterdir(), reverse=True):
        manifest = d / "manifest.json"
        if d.is_dir() and manifest.exists():
            try:
                items.append(json.loads(manifest.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return items


def _rotate(keep: int = KEEP_LAST) -> None:
    backups = list_backups()
    for old in backups[keep:]:
        path = Path(old.get("path") or BACKUPS_DIR / old["id"])
        if path.exists() and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def create_backup(kind: str = "manual", store: GeneStore | None = None) -> dict:
    """
    Копирует genes.sqlite и JSON базы знаний в data/backups/<timestamp>/.
    Перед копированием SQLite делает checkpoint WAL.
    """
    ensure_dirs()
    backup_id = _stamp()
    dest = BACKUPS_DIR / backup_id
    dest.mkdir(parents=True, exist_ok=True)

    own = False
    if store is None and DB_PATH.exists():
        store = GeneStore()
        own = True
    if store is not None:
        try:
            store.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            store.conn.commit()
        except Exception:
            pass

    files = []
    sources = [
        ("genes.sqlite", DB_PATH),
        ("parsed_knowledge_base_clean.json", KB_CLEAN),
        ("parsed_knowledge_base.json", KB_RAW),
    ]
    for name, src in sources:
        if not src.exists():
            continue
        target = dest / name
        shutil.copy2(src, target)
        files.append({
            "name": name,
            "bytes": target.stat().st_size,
            "sha256": _sha256(target),
        })

    combined = hashlib.sha256()
    for f in files:
        combined.update(f["sha256"].encode("ascii"))
        combined.update(b"|")

    meta = {
        "id": backup_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path": str(dest),
        "kind": kind,
        "files": files,
        "sha256": combined.hexdigest() if files else "",
    }
    (dest / "manifest.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    recorder = store
    opened = False
    if recorder is None and DB_PATH.exists():
        try:
            recorder = GeneStore()
            opened = True
        except Exception:
            recorder = None
    if recorder is not None:
        try:
            recorder.record_backup(meta)
        except Exception:
            pass
        if opened:
            recorder.close()
    if own and store is not None:
        store.close()

    _rotate()
    return meta


def restore_backup(backup_id: str, what: str = "all") -> dict:
    """
    Восстанавливает снимок.

    what: all | sqlite | knowledge
    """
    ensure_dirs()
    dest = BACKUPS_DIR / backup_id
    manifest_path = dest / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Бэкап не найден: {backup_id}")
    meta = json.loads(manifest_path.read_text(encoding="utf-8"))

    mapping = {
        "sqlite": [("genes.sqlite", DB_PATH)],
        "knowledge": [
            ("parsed_knowledge_base_clean.json", KB_CLEAN),
            ("parsed_knowledge_base.json", KB_RAW),
        ],
    }
    mapping["all"] = mapping["sqlite"] + mapping["knowledge"]
    if what not in mapping:
        raise ValueError("what должен быть all, sqlite или knowledge")

    restored = []
    for name, target in mapping[what]:
        src = dest / name
        if not src.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        restored.append(name)

    return {"id": backup_id, "restored": restored, "kind": meta.get("kind")}
