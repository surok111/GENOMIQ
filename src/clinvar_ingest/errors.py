"""Errors for the ClinVar staging ingest. Messages stay free of secrets."""


class ClinVarIngestError(Exception):
    """Base error for download, parse, or persistence failures."""


class ClinVarDownloadError(ClinVarIngestError):
    """NCBI FTP download failed or returned a non-success status."""


class ClinVarParseError(ClinVarIngestError):
    """variant_summary.txt.gz could not be read as a tab-delimited table."""


class ClinVarPersistError(ClinVarIngestError):
    """PostgreSQL schema or UPSERT failed. The current batch is rolled back."""
