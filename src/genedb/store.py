"""SQLite-хранилище живой базы генов."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .paths import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS genes (
    symbol TEXT PRIMARY KEY,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    name TEXT,
    chromosome TEXT,
    summary TEXT,
    omim_mim TEXT,
    clinpgx_id TEXT,
    kb_group TEXT,
    last_synced_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS omim_entries (
    mim_number TEXT PRIMARY KEY,
    gene_symbol TEXT NOT NULL,
    title TEXT,
    prefix TEXT,
    phenotypes_json TEXT NOT NULL DEFAULT '[]',
    allelic_variants_json TEXT NOT NULL DEFAULT '[]',
    source TEXT,
    url TEXT,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_omim_gene ON omim_entries(gene_symbol);

CREATE TABLE IF NOT EXISTS clinvar_variants (
    variation_id TEXT NOT NULL,
    gene_symbol TEXT NOT NULL,
    title TEXT,
    classification TEXT,
    review_status TEXT,
    variation_type TEXT,
    rsid TEXT,
    conditions TEXT,
    url TEXT,
    fetched_at TEXT,
    PRIMARY KEY (variation_id, gene_symbol)
);
CREATE INDEX IF NOT EXISTS idx_clinvar_gene ON clinvar_variants(gene_symbol);
CREATE INDEX IF NOT EXISTS idx_clinvar_class ON clinvar_variants(classification);

CREATE TABLE IF NOT EXISTS clinvar_stats (
    gene_symbol TEXT PRIMARY KEY,
    total INTEGER DEFAULT 0,
    pathogenic INTEGER DEFAULT 0,
    likely_pathogenic INTEGER DEFAULT 0,
    vus INTEGER DEFAULT 0,
    likely_benign INTEGER DEFAULT 0,
    benign INTEGER DEFAULT 0,
    conflicting INTEGER DEFAULT 0,
    other INTEGER DEFAULT 0,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS clinpgx_annotations (
    annotation_id TEXT PRIMARY KEY,
    gene_symbol TEXT NOT NULL,
    level TEXT,
    variant TEXT,
    drugs TEXT,
    types TEXT,
    phenotypes TEXT,
    url TEXT,
    payload_json TEXT,
    fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_clinpgx_gene ON clinpgx_annotations(gene_symbol);

CREATE TABLE IF NOT EXISTS clinpgx_labels (
    label_id TEXT PRIMARY KEY,
    gene_symbol TEXT NOT NULL,
    source TEXT,
    name TEXT,
    url TEXT,
    fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    sources TEXT,
    genes_ok INTEGER DEFAULT 0,
    genes_failed INTEGER DEFAULT 0,
    error TEXT,
    backup_id TEXT
);

CREATE TABLE IF NOT EXISTS backup_meta (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    files_json TEXT NOT NULL DEFAULT '[]',
    sha256 TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


class GeneStore:
    def __init__(self, path: Path | None = None):
        ensure_dirs()
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "GeneStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def upsert_gene(self, gene: dict) -> None:
        self.conn.execute(
            """
            INSERT INTO genes(symbol, aliases_json, name, chromosome, summary,
                              omim_mim, clinpgx_id, kb_group, last_synced_at, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                aliases_json=excluded.aliases_json,
                name=COALESCE(excluded.name, genes.name),
                chromosome=COALESCE(excluded.chromosome, genes.chromosome),
                summary=COALESCE(excluded.summary, genes.summary),
                omim_mim=COALESCE(excluded.omim_mim, genes.omim_mim),
                clinpgx_id=COALESCE(excluded.clinpgx_id, genes.clinpgx_id),
                kb_group=COALESCE(excluded.kb_group, genes.kb_group),
                last_synced_at=COALESCE(excluded.last_synced_at, genes.last_synced_at),
                last_error=excluded.last_error
            """,
            (
                gene["symbol"],
                _dumps(gene.get("aliases") or []),
                gene.get("name"),
                gene.get("chromosome"),
                gene.get("summary"),
                gene.get("omim_mim"),
                gene.get("clinpgx_id"),
                gene.get("kb_group"),
                gene.get("last_synced_at"),
                gene.get("last_error"),
            ),
        )
        self.conn.commit()

    def mark_synced(self, symbol: str, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE genes SET last_synced_at=?, last_error=? WHERE symbol=?",
            (_now(), error, symbol),
        )
        self.conn.commit()

    def replace_omim(self, gene_symbol: str, entries: list[dict]) -> None:
        self.conn.execute("DELETE FROM omim_entries WHERE gene_symbol=?", (gene_symbol,))
        for e in entries:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO omim_entries
                (mim_number, gene_symbol, title, prefix, phenotypes_json,
                 allelic_variants_json, source, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(e["mim_number"]),
                    gene_symbol,
                    e.get("title"),
                    e.get("prefix"),
                    _dumps(e.get("phenotypes") or []),
                    _dumps(e.get("allelic_variants") or []),
                    e.get("source"),
                    e.get("url"),
                    _now(),
                ),
            )
        if entries:
            self.conn.execute(
                "UPDATE genes SET omim_mim=? WHERE symbol=?",
                (str(entries[0]["mim_number"]), gene_symbol),
            )
        self.conn.commit()

    def replace_clinvar(self, gene_symbol: str, variants: list[dict], stats: dict) -> None:
        self.conn.execute("DELETE FROM clinvar_variants WHERE gene_symbol=?", (gene_symbol,))
        for v in variants:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO clinvar_variants
                (variation_id, gene_symbol, title, classification, review_status,
                 variation_type, rsid, conditions, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(v["variation_id"]),
                    gene_symbol,
                    v.get("title"),
                    v.get("classification"),
                    v.get("review_status"),
                    v.get("variation_type"),
                    v.get("rsid"),
                    v.get("conditions"),
                    v.get("url"),
                    _now(),
                ),
            )
        self.conn.execute(
            """
            INSERT OR REPLACE INTO clinvar_stats
            (gene_symbol, total, pathogenic, likely_pathogenic, vus,
             likely_benign, benign, conflicting, other, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gene_symbol,
                stats.get("total", 0),
                stats.get("pathogenic", 0),
                stats.get("likely_pathogenic", 0),
                stats.get("vus", 0),
                stats.get("likely_benign", 0),
                stats.get("benign", 0),
                stats.get("conflicting", 0),
                stats.get("other", 0),
                _now(),
            ),
        )
        self.conn.commit()

    def replace_clinpgx(
        self,
        gene_symbol: str,
        clinpgx_id: str | None,
        annotations: list[dict],
        labels: list[dict],
    ) -> None:
        self.conn.execute("DELETE FROM clinpgx_annotations WHERE gene_symbol=?", (gene_symbol,))
        self.conn.execute("DELETE FROM clinpgx_labels WHERE gene_symbol=?", (gene_symbol,))
        for a in annotations:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO clinpgx_annotations
                (annotation_id, gene_symbol, level, variant, drugs, types,
                 phenotypes, url, payload_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(a["annotation_id"]),
                    gene_symbol,
                    a.get("level"),
                    a.get("variant"),
                    a.get("drugs"),
                    a.get("types"),
                    a.get("phenotypes"),
                    a.get("url"),
                    _dumps(a.get("payload") or {}),
                    _now(),
                ),
            )
        for lab in labels:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO clinpgx_labels
                (label_id, gene_symbol, source, name, url, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(lab["label_id"]),
                    gene_symbol,
                    lab.get("source"),
                    lab.get("name"),
                    lab.get("url"),
                    _now(),
                ),
            )
        if clinpgx_id:
            self.conn.execute(
                "UPDATE genes SET clinpgx_id=? WHERE symbol=?",
                (clinpgx_id, gene_symbol),
            )
        self.conn.commit()

    def start_sync_run(self, sources: Iterable[str], backup_id: str | None) -> int:
        cur = self.conn.execute(
            "INSERT INTO sync_runs(started_at, sources, backup_id) VALUES (?, ?, ?)",
            (_now(), ",".join(sources), backup_id),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_sync_run(self, run_id: int, ok: int, failed: int, error: str | None = None) -> None:
        self.conn.execute(
            """
            UPDATE sync_runs
            SET finished_at=?, genes_ok=?, genes_failed=?, error=?
            WHERE id=?
            """,
            (_now(), ok, failed, error, run_id),
        )
        self.conn.commit()

    def record_backup(self, meta: dict) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO backup_meta(id, created_at, path, kind, files_json, sha256)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                meta["id"],
                meta["created_at"],
                meta["path"],
                meta["kind"],
                _dumps(meta.get("files") or []),
                meta.get("sha256"),
            ),
        )
        self.conn.commit()

    def counts(self) -> dict:
        def _one(sql: str) -> int:
            row = self.conn.execute(sql).fetchone()
            return int(row[0]) if row else 0

        last = self.conn.execute(
            "SELECT started_at, finished_at, genes_ok, genes_failed, sources "
            "FROM sync_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "genes": _one("SELECT COUNT(*) FROM genes"),
            "omim_entries": _one("SELECT COUNT(*) FROM omim_entries"),
            "clinvar_variants": _one("SELECT COUNT(*) FROM clinvar_variants"),
            "clinpgx_annotations": _one("SELECT COUNT(*) FROM clinpgx_annotations"),
            "sync_runs": _one("SELECT COUNT(*) FROM sync_runs"),
            "last_sync": dict(last) if last else None,
        }

    def snapshot_for_gene(self, symbol: str) -> dict | None:
        key = symbol.strip().upper()
        gene = self.conn.execute("SELECT * FROM genes WHERE symbol=?", (key,)).fetchone()
        if gene is None:
            row = self.conn.execute(
                "SELECT symbol FROM genes WHERE aliases_json LIKE ?",
                (f'%"{key}"%',),
            ).fetchone()
            if row:
                key = row["symbol"]
                gene = self.conn.execute("SELECT * FROM genes WHERE symbol=?", (key,)).fetchone()
        if gene is None:
            return None

        omim = [dict(r) for r in self.conn.execute(
            "SELECT mim_number, title, prefix, phenotypes_json, allelic_variants_json, url, source "
            "FROM omim_entries WHERE gene_symbol=?",
            (key,),
        )]
        for e in omim:
            e["phenotypes"] = json.loads(e.pop("phenotypes_json") or "[]")
            e["allelic_variants"] = json.loads(e.pop("allelic_variants_json") or "[]")

        stats_row = self.conn.execute(
            "SELECT * FROM clinvar_stats WHERE gene_symbol=?", (key,)
        ).fetchone()
        variants = [dict(r) for r in self.conn.execute(
            """
            SELECT variation_id, title, classification, review_status, rsid, conditions, url
            FROM clinvar_variants
            WHERE gene_symbol=?
            ORDER BY CASE
                WHEN lower(classification) LIKE '%pathogenic%' AND lower(classification) NOT LIKE '%likely%' THEN 0
                WHEN lower(classification) LIKE '%likely pathogenic%' THEN 1
                WHEN lower(classification) LIKE '%conflict%' THEN 2
                ELSE 3
            END, title
            LIMIT 12
            """,
            (key,),
        )]
        pgx = [dict(r) for r in self.conn.execute(
            """
            SELECT annotation_id, level, variant, drugs, types, phenotypes, url
            FROM clinpgx_annotations
            WHERE gene_symbol=?
            ORDER BY CASE level
                WHEN '1A' THEN 0 WHEN '1B' THEN 1 WHEN '2A' THEN 2
                WHEN '2B' THEN 3 WHEN '3' THEN 4 ELSE 5
            END
            LIMIT 12
            """,
            (key,),
        )]
        labels = [dict(r) for r in self.conn.execute(
            "SELECT label_id, source, name, url FROM clinpgx_labels WHERE gene_symbol=? LIMIT 8",
            (key,),
        )]
        return {
            "symbol": key,
            "name": gene["name"],
            "chromosome": gene["chromosome"],
            "summary": gene["summary"],
            "omim_mim": gene["omim_mim"],
            "clinpgx_id": gene["clinpgx_id"],
            "last_synced_at": gene["last_synced_at"],
            "omim": omim,
            "clinvar_stats": dict(stats_row) if stats_row else {},
            "clinvar_highlights": variants,
            "clinpgx_annotations": pgx,
            "clinpgx_labels": labels,
        }
