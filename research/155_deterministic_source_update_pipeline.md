# 155. Deterministic source update pipeline

Accessed 23 November 2026. This is an architecture specification. It does not add a flow, a table, or a scheduler. The existing ClinVar and CPIC ingests are reused only where they already match a stage. They are not treated as a finished production pipeline.

## Stages

| Stage | Required behavior | Existing piece | Gap |
|---|---|---|---|
| 1. Source registry | One record per source: publisher, role, license snapshot, allowed use, endpoint | Document 74 is a claim registry. Document 142 is a research inventory. Neither is a table the ingest reads | No machine-readable registry |
| 2. Release discovery | Find the publisher’s current release identifier without parsing the whole payload | Not present. CPIC uses a live API. ClinVar uses a floating `variant_summary.txt.gz` URL | A download of “latest” does not name the release |
| 3. Artifact download | Store bytes from the official URL. Resume is allowed | ClinVar downloader streams, retries, and resumes. CPIC client pages JSON into memory and the pipeline persists rows | CPIC responses are not first saved as one immutable body |
| 4. Checksum | SHA-256 of the stored bytes. Reject a mismatch if the publisher posted a checksum | ClinVar code verifies gzip CRC only | No stored SHA-256. No publisher checksum is fetched |
| 5. Immutable raw storage | Write-once object keyed by source and checksum | PostgreSQL `raw_payload` on the parsed row. A re-ingest can replace the row’s JSON | The payload is not an immutable file. Two versions of one variant id cannot both be “current” and historical |
| 6. Parsing | A versioned parser emits publisher-shaped records | ClinVar parser and CPIC record mapping exist | ClinVar parser drops rows and assemblies before they are stored. That filter belongs after a complete parse, if it belongs anywhere |
| 7. Schema validation | Required publisher fields present, types checked, unknown columns retained | ClinVar requires three columns. CPIC stores the JSON it received | Unknown ClinVar columns are not all retained. The hash uses a subset |
| 8. Normalization | Left-align, identifier checks, transcript version | Not in the ingest | `KNOWN_VARIANTS` is an unversioned normalizer |
| 9. Identity resolution | Link to internal gene, variant, drug, or disease by the keys in document 153 | ClinVar matches HGNC symbols and aliases from the local knowledge base | Alias match can be wrong. No HGNC release is consulted |
| 10. Duplicate and conflict detection | Apply document 154 | Review queue marks a change named conflict as pending | The ClinVar filter removes conflicting aggregates before the queue |
| 11. Change detection | Compare parsed records to the previous snapshot of the same source | Row hash for a subset of ClinVar fields. CPIC upsert by recommendation id | A condition-only edit can miss the hash. A new CPIC version can overwrite the stored version integer |
| 12. Review queue | Clinical changes wait for a person | `review_queue` policy and hooks. Prefect flows do not publish | The queue is only as complete as the diff it receives |
| 13. Approval | A person approves, rejects, or defers. Approval is not implied by a clean parse | `kb_version` publish requires an approved change | No source-snapshot approval record |
| 14. Publication | A new internal version becomes current | `publish.py` writes a new version and can roll back by writing another | Publication does not record the source checksum |
| 15. Historical retention | Old snapshots and old publications remain readable | Version rows are kept. Source files are not | Cannot reproduce the external text behind an old report |
| 16. Rollback | A new publication points at an older approved state. It does not delete the bad publication | `publish.py` rollback creates a new version | No rollback of a raw snapshot, because snapshots are not yet immutable objects |

## Determinism

Given the same bytes, the same parser version, and the same transform version, the parsed records and the hashes are the same. Live APIs are deterministic only after the body is saved. A scheduled refetch that does not save the body is not a reproducible run.

The Prefect cron expressions are operational timers. They are not a release detector. A Tuesday ClinVar run might download a different weekly file from the previous Tuesday and store only a timestamp.

## What is safe to reuse

| Component | Reuse |
|---|---|
| ClinVar HTTP download with retry and Range resume | The transport. Not the “latest URL only” identity |
| Gzip integrity check | Necessary, not sufficient |
| CPIC client’s paging and retry | The transport, after the pages are written to one artifact |
| Staging tables | A landing area. Add snapshot identity before trusting them as history |
| Review-queue rule that clinical diffs stay pending | Keep. Do not widen `auto_accepted` |
| `kb_version` publication and rollback | The internal version mechanism |
| `pg_backup.py` | Database backup. It does not by itself archive multi-gigabyte source files unless those files are in the database |
| Gene-panel loader | The idea of limiting a worklist. Not as a silent deletion from the archive |

## What is insufficient

- Two ClinVar paths, FTP and E-utilities, with different filters and no shared snapshot id.
- A gene-store sync that writes OMIM and ClinPGx into SQLite. That path is outside the review queue. It must not become publication, and OMIM is not licensed for it.
- `KNOWN_VARIANTS` as an identity source.
- Alias-based gene matching without an HGNC pin.
- A pathogenic-only ClinVar filter presented as ingestion of ClinVar.
- No license snapshot on any ingest.
- No checksum that a later process can recompute from a file.

## Failure behavior

| Failure | Result |
|---|---|
| Download error | Keep the previous snapshot as current. Do not publish an empty release |
| Checksum mismatch | Reject the artifact. Do not parse it |
| Schema change upstream | Quarantine the file, keep unknown columns, and require a parser review. Do not drop the column |
| Partial API paging | Discard the incomplete body. Do not upsert a half catalog over a full one |
| Identity unresolved | Store the external record and mark it unlinked. Do not create a gene |
| Conflict | Store both sides and queue a review. Do not pick one |
| License unresolved | The registry forbids publication. A research download can still be stored in a non-shipped area if counsel has not prohibited the download itself |

## Separation from publication

Ingestion ends at a reviewed snapshot and a queue. Publication is a later act on internal knowledge. A green ingest run is not a new clinical release. The Prefect flows already refuse to publish. The specification keeps that refusal and adds the missing archive underneath it.

## Recommendation

The next implementation, when one is authorized, is a registry row and an immutable file for the two sources that already run: ClinVar and CPIC. Widen ClinVar storage so filtered-out classes remain in the archive even if they stay off the worklist. Do not add PharmVar, OMIM, or ClinPGx to the published path while their licenses are unresolved.
