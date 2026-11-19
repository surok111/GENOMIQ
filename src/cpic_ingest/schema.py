"""PostgreSQL staging tables for CPIC guidelines and recommendations.

Applied by ``migrate_to_pg.py`` and by the ingest pipeline via
``CREATE TABLE IF NOT EXISTS``. A knowledge-base reload does not drop these
tables, and ingest does not write into the clinical knowledge base.
"""

CPIC_STAGING_SQL = """
CREATE TABLE IF NOT EXISTS cpic_guideline (
    id                 BIGINT PRIMARY KEY,
    version            INTEGER NOT NULL,
    clinpgxid          TEXT,
    name               TEXT,
    url                TEXT,
    publication_pmid   TEXT,
    publication_year   INTEGER,
    raw_payload        JSONB NOT NULL,
    source_retrieved_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS cpic_recommendation (
    recommendationid   BIGINT PRIMARY KEY,
    lookupkey          JSONB,
    drugname           TEXT,
    guidelinename      TEXT,
    guidelineurl       TEXT,
    raw_payload        JSONB NOT NULL,
    source_retrieved_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS cpic_recommendation_drug_idx
    ON cpic_recommendation (drugname);
CREATE INDEX IF NOT EXISTS cpic_recommendation_guideline_idx
    ON cpic_recommendation (guidelinename);

CREATE TABLE IF NOT EXISTS cpic_drug_sync (
    drugname   TEXT PRIMARY KEY,
    synced_at  TIMESTAMPTZ NOT NULL
);
"""
