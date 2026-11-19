"""Errors for CPIC staging ingest. Messages stay free of secrets."""


class CpicIngestError(Exception):
    """Base error for CPIC API or persistence failures."""


class CpicApiError(CpicIngestError):
    """CPIC request failed. The message contains the path and status, not secrets."""


class CpicPersistError(CpicIngestError):
    """PostgreSQL schema or UPSERT failed. The current transaction is rolled back."""
