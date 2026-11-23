# 158. Local-first source storage architecture

Accessed 23 November 2026. This is a portable storage design. It does not buy a server, a cloud bucket, or a support contract. It uses a filesystem and PostgreSQL, which the repository already assumes for knowledge staging and versions.

## Principles

The raw publisher bytes and the published knowledge are different stores. Ingestion can succeed and publication can stay still. A machine without a network can render a report from the snapshots it already has. A network is required only to discover and download a new release.

## Layout

| Store | Contents | Technology |
|---|---|---|
| Raw archive | Immutable files, one object per checksum | A directory on local disk. The path is a setting, not a hardcoded drive |
| Source catalog | Registry, snapshot rows, licenses, checksums, retrieval logs | PostgreSQL tables. Not the clinical knowledge tables |
| Parsed landing | Publisher-shaped rows tied to a snapshot id | PostgreSQL. The current `clinvar_staging` and `cpic_*` tables are the seed of this, after they gain a snapshot id |
| Normalized external entities | The transform output | PostgreSQL, separate schema or table prefix from internal knowledge |
| Internal knowledge and versions | Genes, claims, rules, publications | Existing `kb_version` design |
| Review | Pending diffs | Existing review queue |
| Backups | Copies of the catalog, the knowledge database, and the raw directory | Existing `pg_backup.py` plus a file-level copy of the raw directory |

Object storage can later mirror the raw directory if the checksum is the key. The logical design does not require it. A USB disk and a laptop directory are a valid deployment of the same layout.

## Object key

`{source_id}/{publisher_release}/{sha256}.{ext}`

The release component is the publisher’s name, sanitized. The checksum is the identity. A second download of the same bytes does not create a second object. A corrected file with a new checksum does. Deduplication is by checksum, not by release name, because ClinVar can replace a monthly file.

## PostgreSQL

The catalog holds the fields in document 152. Parsed rows hold a foreign key to the snapshot. They do not hold a second copy of a multi-gigabyte VCF. Large files stay on disk. JSON snapshots of API responses are small enough to store either as a file in the raw archive or as `jsonb`. One of those, not both, is the canonical bytes. The other can be a cache.

The existing staging tables already use PostgreSQL and `raw_payload`. The change is to stop treating that payload as the only copy and to stop updating it in place. A new snapshot inserts new rows. Current is a pointer.

SQLite, used by `src/genedb/store.py` for OMIM and ClinPGx, is not the catalog. Putting licensed-uncleared narrative in a side database makes the license boundary harder to see. New source snapshots go to the PostgreSQL catalog and the raw directory. The SQLite gene store is not extended.

## Growth

Sizes were not measured, because the large files were not downloaded. The design still has to admit them.

| Object | Expectation | Handling |
|---|---|---|
| CPIC JSON and workbooks | Small | Keep every snapshot |
| ClinVar `variant_summary` gzip | Large relative to the JSON, still a single file | Keep monthly archives. A weekly file that was not the archived month can be discarded after the monthly checksum is stored, except the week a report cited |
| ClinVar XML | Larger than the summary | Tier 2. Do not download until the summary archive is in place |
| gnomAD sites | Large | One pinned release, compressed, with restricted annotation columns removed into a non-shipped sidecar or not downloaded |
| HPO and MONDO | Small | Keep the releases that reports cite |
| FASTA | One per build | Content-addressed. Do not keep casual duplicates |

No number above is a measured byte count.

## Network and offline use

| Operation | Network |
|---|---|
| Discover and download | Required. Failure leaves the previous pointer in place |
| Parse, review, publish, render a pinned report | Not required |
| NCBI E-utilities or a live CPIC read during a report | Forbidden. The report reads the snapshot |

A failed download, a checksum mismatch, or a half-written file is deleted or marked incomplete and is not parsed. The ClinVar client’s `.part` resume can stay. A resumed file still has to pass SHA-256 before it is renamed into the archive.

## Backup and restore

A restore is consistent only if the database snapshot and the raw directory are from the same backup set. Restoring the database without the files, or the files without the catalog, breaks the checksum link. `pg_backup.py` covers the database. The raw directory needs the same schedule and the same retention. This specification does not pick a vendor command.

A restore does not contact the publishers and does not “refresh to latest.”

## Reproducibility

A publication record stores snapshot ids. A second machine with those files and that publication row renders the same citations. Parser version is part of the parsed generation, so the binaries or the git revision of the parser are recorded too. A backup that omits the parser revision can still show the stored sentences. It cannot honestly claim they can be regenerated.

## Separation

The ingest user can write the catalog and the raw directory. The publication user can write `kb_version` only from an approved queue item. The same operating-system account on a single workstation can do both jobs, but the code paths stay separate, as the Prefect flows and `publish.py` already are. A download job must not import `publish`.

## What this design does not add

A new database server. A queue service beyond the existing review tables. A search cluster. An ontology reasoner. A running annotator. Those can wait until a tier 1 file is actually pinned.

## Recommendation

Point the next ClinVar and CPIC runs at a content-addressed directory and a snapshot row, on the machine that already runs PostgreSQL. Keep the raw directory in the backup set. Do not place OMIM or ClinPGx narrative in that directory until document 151’s legal flags are cleared.
