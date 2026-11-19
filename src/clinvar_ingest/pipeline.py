"""ClinVar ingest: download, filter, hash, and stage. Each step is separate."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .download import VARIANT_SUMMARY_URL, download_variant_summary
from .errors import ClinVarIngestError, ClinVarPersistError
from .panel import load_hgnc_panel
from .parser import dedupe_variation, iter_retained_chunks
from .upsert import UpsertStats, ensure_clinvar_schema, upsert_records

DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "clinvar" / "variant_summary.txt.gz"


def ingest_clinvar(
    database_url: str,
    source: str | Path | None = None,
    panel: set[str] | None = None,
    chunksize: int = 50_000,
    cache_path: Path | None = None,
    download_url: str = VARIANT_SUMMARY_URL,
) -> dict:
    """Load pathogenic panel variants into ``clinvar_staging``.

    ``source`` is a local ``variant_summary.txt.gz``. When it is omitted the
    file is streamed from NCBI FTP into ``cache_path`` first. The gene panel
    defaults to the knowledge-base HGNC symbols.
    """
    if not database_url or not str(database_url).strip():
        raise ClinVarPersistError("DATABASE_URL is empty")
    if "YOUR_PASSWORD" in database_url:
        raise ClinVarPersistError("DATABASE_URL still contains the placeholder password")

    gene_panel = panel if panel is not None else load_hgnc_panel()
    if not gene_panel:
        raise ClinVarIngestError("HGNC gene panel is empty")

    downloaded = False
    if source is None:
        dest = cache_path or DEFAULT_CACHE
        source = download_variant_summary(dest, url=download_url)
        downloaded = True

    retrieved_at = datetime.now(timezone.utc)
    stats = UpsertStats()
    matched = 0
    skipped_invalid = 0
    locked_grch38: set[int] = set()

    import psycopg

    try:
        conn = psycopg.connect(database_url)
    except Exception as exc:
        raise ClinVarPersistError("Could not connect to PostgreSQL") from exc

    try:
        ensure_clinvar_schema(conn)
        conn.commit()
        for rows in iter_retained_chunks(source, gene_panel, chunksize=chunksize):
            kept: list[dict] = []
            for record in rows:
                variation = str(record.get("VariationID") or "").strip()
                if not variation.isdigit():
                    skipped_invalid += 1
                    continue
                matched += 1
                kept.append(record)
            batch = dedupe_variation(kept, locked_grch38)
            if not batch:
                continue
            stats.add(upsert_records(conn, batch, retrieved_at))
            conn.commit()
    except ClinVarIngestError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise ClinVarIngestError(f"ClinVar ingest stopped: {exc.__class__.__name__}") from exc
    finally:
        conn.close()

    return {
        "downloaded": downloaded,
        "source": str(source),
        "panel_size": len(gene_panel),
        "matched": matched,
        "inserted": stats.inserted,
        "updated": stats.updated,
        "unchanged": stats.unchanged,
        "skipped_invalid": skipped_invalid,
        "source_retrieved_at": retrieved_at.isoformat(),
    }
