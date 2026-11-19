"""Idempotent UPSERT into the CPIC staging tables."""

from __future__ import annotations

from datetime import datetime

import psycopg
from psycopg.types.json import Json

from .errors import CpicPersistError
from .schema import CPIC_STAGING_SQL

GUIDELINE_UPSERT_SQL = """
INSERT INTO cpic_guideline (
    id, version, clinpgxid, name, url,
    publication_pmid, publication_year, raw_payload, source_retrieved_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (id) DO UPDATE SET
    version = EXCLUDED.version,
    clinpgxid = EXCLUDED.clinpgxid,
    name = EXCLUDED.name,
    url = EXCLUDED.url,
    publication_pmid = EXCLUDED.publication_pmid,
    publication_year = EXCLUDED.publication_year,
    raw_payload = EXCLUDED.raw_payload,
    source_retrieved_at = EXCLUDED.source_retrieved_at
WHERE cpic_guideline.version < EXCLUDED.version
RETURNING id
"""

RECOMMENDATION_UPSERT_SQL = """
INSERT INTO cpic_recommendation (
    recommendationid, lookupkey, drugname, guidelinename, guidelineurl,
    raw_payload, source_retrieved_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s
)
ON CONFLICT (recommendationid) DO UPDATE SET
    lookupkey = EXCLUDED.lookupkey,
    drugname = EXCLUDED.drugname,
    guidelinename = EXCLUDED.guidelinename,
    guidelineurl = EXCLUDED.guidelineurl,
    raw_payload = EXCLUDED.raw_payload,
    source_retrieved_at = EXCLUDED.source_retrieved_at
WHERE cpic_recommendation.lookupkey IS DISTINCT FROM EXCLUDED.lookupkey
   OR cpic_recommendation.drugname IS DISTINCT FROM EXCLUDED.drugname
   OR cpic_recommendation.guidelinename IS DISTINCT FROM EXCLUDED.guidelinename
   OR cpic_recommendation.guidelineurl IS DISTINCT FROM EXCLUDED.guidelineurl
   OR cpic_recommendation.raw_payload IS DISTINCT FROM EXCLUDED.raw_payload
RETURNING recommendationid
"""


def ensure_cpic_schema(conn) -> None:
    """Create CPIC staging tables when they are missing. Does not touch existing rows."""
    try:
        conn.execute(CPIC_STAGING_SQL)
    except psycopg.Error as exc:
        raise CpicPersistError("Could not create CPIC staging tables") from exc


def load_guideline_versions(conn) -> dict[int, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, version FROM cpic_guideline")
        return {int(row[0]): int(row[1]) for row in cur.fetchall()}


def load_synced_drugs(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT drugname FROM cpic_drug_sync")
        return {str(row[0]) for row in cur.fetchall()}


def load_recommendation_guidelines(conn) -> dict[str, set[str]]:
    """drugname -> guideline names already stored for that drug."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT drugname, guidelinename
            FROM cpic_recommendation
            WHERE drugname IS NOT NULL AND guidelinename IS NOT NULL
            """
        )
        grouped: dict[str, set[str]] = {}
        for drugname, guidelinename in cur.fetchall():
            grouped.setdefault(str(drugname), set()).add(str(guidelinename))
        return grouped


def upsert_guideline(conn, row: dict, retrieved_at: datetime) -> str:
    """Insert a new guideline or update it when the version increased.

    Returns ``inserted``, ``updated``, or ``unchanged``. A same-or-lower version
    does not rewrite publication year or any other column.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM cpic_guideline WHERE id = %s", (row["id"],))
        existing = cur.fetchone()
        cur.execute(
            GUIDELINE_UPSERT_SQL,
            (
                row["id"],
                row["version"],
                row.get("clinpgxid"),
                row.get("name"),
                row.get("url"),
                row.get("publication_pmid"),
                row.get("publication_year"),
                Json(row.get("raw_payload") or {}),
                retrieved_at,
            ),
        )
        written = cur.fetchone()
    if existing is None:
        if written is None:
            raise CpicPersistError(f"UPSERT did not insert guideline {row['id']}")
        return "inserted"
    if int(existing[0]) < int(row["version"]):
        if written is None:
            raise CpicPersistError(f"UPSERT did not update guideline {row['id']}")
        return "updated"
    if written is not None:
        raise CpicPersistError(f"UPSERT rewrote unchanged guideline {row['id']}")
    return "unchanged"


def upsert_recommendation(conn, row: dict, retrieved_at: datetime) -> str:
    """Insert or update one recommendation. Identical content is left untouched."""
    lookup = row.get("lookupkey")
    lookup_param = None if lookup is None else Json(lookup)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT lookupkey, drugname, guidelinename, guidelineurl, raw_payload
            FROM cpic_recommendation
            WHERE recommendationid = %s
            """,
            (row["recommendationid"],),
        )
        existing = cur.fetchone()
        cur.execute(
            RECOMMENDATION_UPSERT_SQL,
            (
                row["recommendationid"],
                lookup_param,
                row.get("drugname"),
                row.get("guidelinename"),
                row.get("guidelineurl"),
                Json(row.get("raw_payload") or {}),
                retrieved_at,
            ),
        )
        written = cur.fetchone()
    if existing is None:
        if written is None:
            raise CpicPersistError(
                f"UPSERT did not insert recommendation {row['recommendationid']}"
            )
        return "inserted"
    changed = (
        existing[0] != lookup
        or existing[1] != row.get("drugname")
        or existing[2] != row.get("guidelinename")
        or existing[3] != row.get("guidelineurl")
        or existing[4] != (row.get("raw_payload") or {})
    )
    if changed:
        if written is None:
            raise CpicPersistError(
                f"UPSERT did not update recommendation {row['recommendationid']}"
            )
        return "updated"
    if written is not None:
        raise CpicPersistError(
            f"UPSERT rewrote unchanged recommendation {row['recommendationid']}"
        )
    return "unchanged"


def delete_stale_recommendations(conn, drugname: str, guidelinenames: set[str], keep_ids: set[int]) -> int:
    """Remove recommendations for refreshed guidelines that the API no longer returns."""
    if not guidelinenames:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM cpic_recommendation
            WHERE drugname = %s
              AND guidelinename = ANY(%s)
              AND NOT (recommendationid = ANY(%s))
            """,
            (drugname, list(guidelinenames), list(keep_ids)),
        )
        return cur.rowcount


def mark_drug_synced(conn, drugname: str, retrieved_at: datetime) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cpic_drug_sync (drugname, synced_at)
            VALUES (%s, %s)
            ON CONFLICT (drugname) DO UPDATE SET synced_at = EXCLUDED.synced_at
            """,
            (drugname, retrieved_at),
        )
