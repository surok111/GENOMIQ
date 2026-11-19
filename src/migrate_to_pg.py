"""
migrate_to_pg.py — load parsed_knowledge_base_clean.json into PostgreSQL.

Usage (from repo root):
  python src/migrate_to_pg.py

Requires DATABASE_URL in .env, e.g.:
  DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/postgres

Tables: kb_groups, kb_genes, kb_sections, kb_genotypes, kb_pgx, kb_recommendations.
The earlier flat `genes` table is dropped; the interpreter reads these tables.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

import psycopg
from psycopg.types.json import Json

from clinvar_ingest.schema import CLINVAR_STAGING_SQL
from cpic_ingest.schema import CPIC_STAGING_SQL
from interpreter import BASE_PATH, _strip_md, extract_gene_name

KB_PATH = ROOT / BASE_PATH

SCHEMA_SQL = """
DROP TABLE IF EXISTS kb_pgx, kb_genotypes, kb_recommendations, kb_sections, kb_genes, kb_groups CASCADE;
DROP TABLE IF EXISTS genes;

CREATE TABLE kb_groups (
    id            BIGSERIAL PRIMARY KEY,
    ord           INTEGER NOT NULL,
    group_name    TEXT NOT NULL,
    source_file   TEXT,
    intro         TEXT,
    interactions  JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE kb_genes (
    id          BIGSERIAL PRIMARY KEY,
    group_id    BIGINT NOT NULL REFERENCES kb_groups(id) ON DELETE CASCADE,
    ord         INTEGER NOT NULL,
    gene_num    INTEGER,
    gene_name   TEXT NOT NULL,
    header      TEXT NOT NULL,
    intro       TEXT
);

CREATE TABLE kb_sections (
    id         BIGSERIAL PRIMARY KEY,
    gene_id    BIGINT NOT NULL REFERENCES kb_genes(id) ON DELETE CASCADE,
    ord        INTEGER NOT NULL,
    code       TEXT,
    title      TEXT,
    body_text  TEXT
);

CREATE TABLE kb_genotypes (
    id          BIGSERIAL PRIMARY KEY,
    section_id  BIGINT NOT NULL REFERENCES kb_sections(id) ON DELETE CASCADE,
    table_ord   INTEGER NOT NULL,
    row_ord     INTEGER NOT NULL,
    headers     JSONB NOT NULL,
    genotype    TEXT,
    phenotype   TEXT,
    risk        TEXT,
    acmg        TEXT,
    row_data    JSONB NOT NULL
);

CREATE TABLE kb_pgx (
    id          BIGSERIAL PRIMARY KEY,
    section_id  BIGINT NOT NULL REFERENCES kb_sections(id) ON DELETE CASCADE,
    table_ord   INTEGER NOT NULL,
    row_ord     INTEGER NOT NULL,
    headers     JSONB NOT NULL,
    row_data    JSONB NOT NULL
);

CREATE TABLE kb_recommendations (
    id          BIGSERIAL PRIMARY KEY,
    section_id  BIGINT NOT NULL REFERENCES kb_sections(id) ON DELETE CASCADE,
    ord         INTEGER NOT NULL,
    body        TEXT NOT NULL
);

CREATE INDEX kb_genes_name_idx ON kb_genes (gene_name);
CREATE INDEX kb_genotypes_gt_idx ON kb_genotypes (genotype);
CREATE INDEX kb_genotypes_section_idx ON kb_genotypes (section_id, table_ord, row_ord);
CREATE INDEX kb_pgx_section_idx ON kb_pgx (section_id, table_ord, row_ord);
""" + CLINVAR_STAGING_SQL + CPIC_STAGING_SQL


def _cell(row: dict, keys: list[str]) -> str:
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for key in keys:
        if key in low and low[key] not in (None, ""):
            return _strip_md(str(low[key]))
        for rk, rv in low.items():
            if key in rk and rv not in (None, ""):
                return _strip_md(str(rv))
    return ""


def migrate(database_url: str, kb_path: Path = KB_PATH) -> dict[str, int]:
    kb = json.loads(kb_path.read_text(encoding="utf-8"))
    counts = {
        "groups": 0,
        "genes": 0,
        "sections": 0,
        "genotypes": 0,
        "pgx": 0,
        "recommendations": 0,
    }

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            for g_ord, group in enumerate(kb or []):
                cur.execute(
                    """
                    INSERT INTO kb_groups (ord, group_name, source_file, intro, interactions)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        g_ord,
                        str(group.get("group") or "Прочее"),
                        group.get("file") or None,
                        group.get("intro") or None,
                        Json(group.get("interactions") or []),
                    ),
                )
                group_id = cur.fetchone()[0]
                counts["groups"] += 1

                for gene_ord, gene in enumerate(group.get("genes") or []):
                    header = str(gene.get("header") or "").strip()
                    gene_name = (extract_gene_name(header) or header.split(" ")[0] or "UNKNOWN").strip()
                    cur.execute(
                        """
                        INSERT INTO kb_genes (group_id, ord, gene_num, gene_name, header, intro)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            group_id,
                            gene_ord,
                            gene.get("num"),
                            gene_name,
                            header or gene_name,
                            gene.get("intro") or None,
                        ),
                    )
                    gene_id = cur.fetchone()[0]
                    counts["genes"] += 1

                    for sec_ord, sec in enumerate(gene.get("sections") or []):
                        cur.execute(
                            """
                            INSERT INTO kb_sections (gene_id, ord, code, title, body_text)
                            VALUES (%s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                gene_id,
                                sec_ord,
                                sec.get("code") or None,
                                sec.get("title") or None,
                                sec.get("text") or None,
                            ),
                        )
                        section_id = cur.fetchone()[0]
                        counts["sections"] += 1

                        for table_ord, tbl in enumerate(sec.get("tables") or []):
                            headers = tbl.get("headers") or []
                            for row_ord, row in enumerate(tbl.get("rows") or []):
                                cur.execute(
                                    """
                                    INSERT INTO kb_genotypes
                                        (section_id, table_ord, row_ord, headers,
                                         genotype, phenotype, risk, acmg, row_data)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        section_id,
                                        table_ord,
                                        row_ord,
                                        Json(headers),
                                        _cell(row, ["генотип", "genotype", "аллели"]) or None,
                                        _cell(row, ["фенотип", "phenotype"]) or None,
                                        _cell(row, ["клинический риск", "спортивный профиль", "риск"]) or None,
                                        _cell(row, ["acmg"]) or None,
                                        Json(row),
                                    ),
                                )
                                counts["genotypes"] += 1

                        for table_ord, tbl in enumerate(sec.get("pharmacogenomics") or []):
                            headers = tbl.get("headers") or []
                            for row_ord, row in enumerate(tbl.get("rows") or []):
                                cur.execute(
                                    """
                                    INSERT INTO kb_pgx
                                        (section_id, table_ord, row_ord, headers, row_data)
                                    VALUES (%s, %s, %s, %s, %s)
                                    """,
                                    (section_id, table_ord, row_ord, Json(headers), Json(row)),
                                )
                                counts["pgx"] += 1

                        for rec_ord, bullet in enumerate(sec.get("bullets") or []):
                            body = _strip_md(str(bullet)).strip()
                            if not body:
                                continue
                            cur.execute(
                                """
                                INSERT INTO kb_recommendations (section_id, ord, body)
                                VALUES (%s, %s, %s)
                                """,
                                (section_id, rec_ord, body),
                            )
                            counts["recommendations"] += 1
        conn.commit()
    return counts


def _mask_database_url(url: str) -> str:
    """postgres://user:***@host:port/db — never print the password."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return "<unparseable>"
    user = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    db = parsed.path or ""
    scheme = parsed.scheme or "postgresql"
    return f"{scheme}://{user}:***@{host}{port}{db}"


def _password_is_placeholder(url: str) -> bool:
    from urllib.parse import urlparse, unquote

    if not url or "YOUR_PASSWORD" in url:
        return True
    try:
        password = unquote(urlparse(url).password or "")
    except Exception:
        return True
    return password.strip() in {"", "YOUR_PASSWORD"}


def _read_database_url() -> str:
    """Load DATABASE_URL from the project-root .env (KEY=VALUE or a bare postgres URL)."""
    env_path = ROOT / ".env"
    if load_dotenv:
        load_dotenv(env_path, override=True)
    url = (os.getenv("DATABASE_URL") or "").strip().strip('"').strip("'")
    if url:
        return url
    if not env_path.is_file():
        return ""
    text = env_path.read_text(encoding="utf-8-sig")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("database_url="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
        if line.startswith(("postgresql://", "postgres://")):
            return line
    return ""


def main() -> None:
    env_path = ROOT / ".env"
    url = _read_database_url()
    print(f"Env file: {env_path} ({'found' if env_path.is_file() else 'missing'})")
    print(f"DATABASE_URL: {_mask_database_url(url) if url else '<empty>'}")
    if _password_is_placeholder(url):
        raise SystemExit(
            "DATABASE_URL is missing or still uses the YOUR_PASSWORD placeholder.\n"
            f"Expected a line in {env_path}:\n"
            "  DATABASE_URL=postgresql://postgres:<password>@localhost:5432/postgres"
        )
    if not KB_PATH.is_file():
        raise SystemExit(f"Knowledge base not found: {KB_PATH}")

    print(f"Reading {KB_PATH} …")
    counts = migrate(url)
    print(
        "Inserted "
        f"{counts['groups']} groups, {counts['genes']} genes, {counts['sections']} sections, "
        f"{counts['genotypes']} genotypes, {counts['pgx']} drug rows, "
        f"{counts['recommendations']} recommendations"
    )
    print()
    print("Verify in psql:")
    print("  SELECT COUNT(*) FROM kb_genotypes;")
    print("  SELECT COUNT(*) FROM kb_pgx;")
    print("  SELECT COUNT(*) FROM kb_recommendations;")


if __name__ == "__main__":
    main()
