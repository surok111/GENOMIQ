"""Fetch CPIC guidelines and recommendations into staging tables."""

from __future__ import annotations

from datetime import datetime, timezone

from .client import CpicClient
from .drugs import drugs_mentioned, load_drug_names, unique_drugs
from .errors import CpicPersistError
from .records import guideline_action, normalize_guideline, normalize_recommendation
from .store import (
    delete_stale_recommendations,
    ensure_cpic_schema,
    load_guideline_versions,
    load_recommendation_guidelines,
    load_synced_drugs,
    mark_drug_synced,
    upsert_guideline,
    upsert_recommendation,
)


def drugs_to_refresh(
    drugs: list[str],
    *,
    changed_names: set[str],
    changed_drug_names: set[str],
    synced: set[str],
    stored_by_drug: dict[str, set[str]],
) -> list[str]:
    """Drugs with no prior fetch, or drugs tied to a guideline whose version changed."""
    selected: list[str] = []
    changed_folded = {name.casefold() for name in changed_names}
    changed_drugs_folded = {name.casefold() for name in changed_drug_names}
    synced_folded = {name.casefold() for name in synced}
    for drug in drugs:
        folded = drug.casefold()
        if folded not in synced_folded:
            selected.append(drug)
            continue
        if folded in changed_drugs_folded:
            selected.append(drug)
            continue
        stored_names = {name.casefold() for name in stored_by_drug.get(drug, ())}
        if stored_names & changed_folded:
            selected.append(drug)
    return selected


async def ingest_cpic(
    database_url: str,
    *,
    drugs: list[str] | None = None,
    client: CpicClient | None = None,
) -> dict:
    """Load CPIC guidelines and the recommendations for GenomIQ drugs.

    ``drugs`` is only for tests. The CLI leaves it empty so names are read
    from ``kb_pgx``. Staging rows are not copied into the clinical knowledge base.
    """
    if not database_url or not str(database_url).strip():
        raise CpicPersistError("DATABASE_URL is empty")
    if "YOUR_PASSWORD" in database_url:
        raise CpicPersistError("DATABASE_URL still contains the placeholder password")

    import psycopg

    try:
        conn = psycopg.connect(database_url)
    except Exception as exc:
        raise CpicPersistError("Could not connect to PostgreSQL") from exc

    own_client = client is None
    client = client or CpicClient()
    try:
        ensure_cpic_schema(conn)
        conn.commit()
        if drugs is None:
            drugs = load_drug_names(conn)
        else:
            drugs = unique_drugs([drug.strip() for drug in drugs if drug and drug.strip()])
        stored_versions = load_guideline_versions(conn)
        synced = load_synced_drugs(conn)
        stored_by_drug = load_recommendation_guidelines(conn)
        conn.commit()
        conn.close()

        async with client:
            raw_guidelines = await client.fetch_guidelines()
            guidelines = []
            skipped_guidelines = 0
            for raw in raw_guidelines:
                normalized = normalize_guideline(raw)
                if normalized is None:
                    skipped_guidelines += 1
                    continue
                guidelines.append(normalized)

            changed_names: set[str] = set()
            changed_drug_names: set[str] = set()
            for row in guidelines:
                action = guideline_action(stored_versions.get(row["id"]), row["version"])
                if action == "unchanged":
                    continue
                if row.get("name"):
                    changed_names.add(row["name"])
                changed_drug_names.update(drugs_mentioned(row["raw_payload"]))

            refresh = drugs_to_refresh(
                drugs,
                changed_names=changed_names,
                changed_drug_names=changed_drug_names,
                synced=synced,
                stored_by_drug=stored_by_drug,
            )
            recommendations_by_drug: dict[str, list[dict]] = {}
            for drug in refresh:
                fetched = await client.fetch_recommendations(drug)
                normalized_rows = []
                for raw in fetched:
                    item = normalize_recommendation(raw, fallback_drug=drug)
                    if item is not None:
                        normalized_rows.append(item)
                recommendations_by_drug[drug] = normalized_rows

        retrieved_at = datetime.now(timezone.utc)
        try:
            conn = psycopg.connect(database_url)
        except Exception as exc:
            raise CpicPersistError("Could not connect to PostgreSQL") from exc
        counts = {
            "guidelines_inserted": 0,
            "guidelines_updated": 0,
            "guidelines_unchanged": 0,
            "recommendations_inserted": 0,
            "recommendations_updated": 0,
            "recommendations_unchanged": 0,
            "recommendations_removed": 0,
        }
        try:
            for row in guidelines:
                action = guideline_action(stored_versions.get(row["id"]), row["version"])
                if action == "unchanged":
                    counts["guidelines_unchanged"] += 1
                    continue
                outcome = upsert_guideline(conn, row, retrieved_at)
                counts[f"guidelines_{outcome}"] += 1
            for drug, rows in recommendations_by_drug.items():
                keep_ids = {row["recommendationid"] for row in rows}
                for row in rows:
                    outcome = upsert_recommendation(conn, row, retrieved_at)
                    counts[f"recommendations_{outcome}"] += 1
                counts["recommendations_removed"] += delete_stale_recommendations(
                    conn,
                    drug,
                    changed_names,
                    keep_ids,
                )
                mark_drug_synced(conn, drug, retrieved_at)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return {
            "guidelines_fetched": len(guidelines),
            "guidelines_skipped": skipped_guidelines,
            "drugs": len(drugs),
            "drugs_refreshed": len(refresh),
            **counts,
            "source_retrieved_at": retrieved_at.isoformat(),
        }
    finally:
        if conn is not None and not conn.closed:
            conn.close()
        if own_client:
            await client.aclose()
