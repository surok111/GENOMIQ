"""Atomic UPSERT into clinvar_staging.

New variation ids are inserted. A changed content hash updates the row.
The same hash leaves the stored row untouched, including columns that are
not part of the hash (for example RCVaccession).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Json

from .errors import ClinVarPersistError
from .hashing import canonical_hash
from .schema import CLINVAR_STAGING_SQL

# The conflict action must be DO UPDATE with a hash guard.
# ON CONFLICT DO NOTHING is intentionally not used.
UPSERT_SQL = """
INSERT INTO clinvar_staging (
    clinvar_variation_id,
    rcv_accession,
    gene_symbol,
    gene_id,
    clinical_significance,
    content_sha256,
    raw_payload,
    source_retrieved_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (clinvar_variation_id) DO UPDATE SET
    rcv_accession = EXCLUDED.rcv_accession,
    gene_symbol = EXCLUDED.gene_symbol,
    gene_id = EXCLUDED.gene_id,
    clinical_significance = EXCLUDED.clinical_significance,
    content_sha256 = EXCLUDED.content_sha256,
    raw_payload = EXCLUDED.raw_payload,
    source_retrieved_at = EXCLUDED.source_retrieved_at
WHERE clinvar_staging.content_sha256 IS DISTINCT FROM EXCLUDED.content_sha256
RETURNING clinvar_variation_id
"""


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    def add(self, other: "UpsertStats") -> None:
        self.inserted += other.inserted
        self.updated += other.updated
        self.unchanged += other.unchanged


def ensure_clinvar_schema(conn) -> None:
    """Create clinvar_staging when it is missing. Does not touch existing rows."""
    try:
        conn.execute(CLINVAR_STAGING_SQL)
    except psycopg.Error as exc:
        raise ClinVarPersistError("Could not create clinvar_staging") from exc


def _optional_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    return int(text)


def _raw_payload(record: dict) -> dict:
    payload: dict[str, Any] = {}
    for key, value in record.items():
        if value is None:
            payload[str(key)] = None
        else:
            payload[str(key)] = str(value)
    return payload


def _variation_id(record: dict) -> int | None:
    text = str(record.get("VariationID") or "").strip()
    if not text.isdigit():
        return None
    return int(text)


def upsert_records(conn, records: list[dict], retrieved_at: datetime) -> UpsertStats:
    """Insert or update one batch. Unchanged hashes are not written.

    On a database error the connection is rolled back and
    ``ClinVarPersistError`` is raised.
    """
    prepared: list[tuple] = []
    ids: list[int] = []
    hashes: dict[int, str] = {}
    for record in records:
        variation_id = _variation_id(record)
        if variation_id is None:
            continue
        digest = canonical_hash(record)
        ids.append(variation_id)
        hashes[variation_id] = digest
        prepared.append(
            (
                variation_id,
                (str(record.get("RCVaccession")).strip() or None)
                if record.get("RCVaccession") not in (None, "")
                else None,
                (str(record.get("GeneSymbol")).strip() or None)
                if record.get("GeneSymbol") not in (None, "")
                else None,
                _optional_int(record.get("GeneID")),
                (str(record.get("ClinicalSignificance")).strip() or None)
                if record.get("ClinicalSignificance") not in (None, "")
                else None,
                digest,
                Json(_raw_payload(record)),
                retrieved_at,
            )
        )
    collapsed: dict[int, tuple] = {}
    for params in prepared:
        collapsed[int(params[0])] = params
    prepared = list(collapsed.values())
    hashes = {int(params[0]): str(params[5]) for params in prepared}
    ids = list(hashes)
    if not prepared:
        return UpsertStats()

    stats = UpsertStats()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT clinvar_variation_id, content_sha256
                FROM clinvar_staging
                WHERE clinvar_variation_id = ANY(%s)
                """,
                (ids,),
            )
            existing = {
                int(row[0]): (str(row[1]).strip() if row[1] is not None else "")
                for row in cur.fetchall()
            }
            written: set[int] = set()
            for params in prepared:
                cur.execute(UPSERT_SQL, params)
                returned = cur.fetchone()
                if returned is not None:
                    written.add(int(returned[0]))
            for variation_id, digest in hashes.items():
                was_written = variation_id in written
                if variation_id not in existing:
                    if not was_written:
                        raise ClinVarPersistError(
                            f"UPSERT did not insert variation {variation_id}"
                        )
                    stats.inserted += 1
                elif existing[variation_id] != digest:
                    if not was_written:
                        raise ClinVarPersistError(
                            f"UPSERT did not update variation {variation_id}"
                        )
                    stats.updated += 1
                else:
                    if was_written:
                        raise ClinVarPersistError(
                            f"UPSERT rewrote unchanged variation {variation_id}"
                        )
                    stats.unchanged += 1
    except ClinVarPersistError:
        conn.rollback()
        raise
    except psycopg.Error as exc:
        conn.rollback()
        raise ClinVarPersistError("ClinVar staging upsert failed") from exc
    return stats
