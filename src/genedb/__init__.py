"""
Живая база генов: OMIM, ClinVar, ClinPGx + бэкапы.

Публичный API пакета:
    from genedb.store import GeneStore
    from genedb.sync import sync_genes
    from genedb.backup import create_backup, restore_backup, list_backups
    from genedb.enrich import attach_live_db
"""

from .backup import create_backup, list_backups, restore_backup
from .enrich import attach_live_db
from .store import GeneStore
from .sync import sync_genes

__all__ = [
    "GeneStore",
    "sync_genes",
    "create_backup",
    "restore_backup",
    "list_backups",
    "attach_live_db",
]
