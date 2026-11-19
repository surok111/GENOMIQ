"""PostgreSQL staging table for ClinVar variant_summary rows.

Applied by ``migrate_to_pg.py`` (existing knowledge-base migration) and by the
ingest pipeline via ``CREATE TABLE IF NOT EXISTS``. The knowledge-base reload
does not drop this table.
"""

CLINVAR_STAGING_SQL = """
CREATE TABLE IF NOT EXISTS clinvar_staging (
    clinvar_variation_id BIGINT PRIMARY KEY,
    rcv_accession TEXT,
    gene_symbol TEXT,
    gene_id INTEGER,
    clinical_significance TEXT,
    content_sha256 CHAR(64),
    raw_payload JSONB,
    source_retrieved_at TIMESTAMPTZ
);
"""
