# 152. Source versioning and snapshot model

Accessed 23 November 2026. This is a local specification. It is not a schema migration. It extends the provenance entities in document 79 with the dates a source update actually has. Historical bytes are kept. A new release is a new snapshot. It does not overwrite the old one.

## Dates that must not be collapsed

| Date | What it is | Example |
|---|---|---|
| Source release | The publisher’s version or file name | ClinVar monthly archive name. CPIC guideline version integer. MANE v1.5. gnomAD v4.1, dated 19 April 2024 on the policies page |
| Publication date | When the publisher issued that release or the paper | A guideline’s journal date. Not the day GenomIQ noticed it |
| Retrieval timestamp | When this system finished a download | `source_retrieved_at`, already stored for CPIC and ClinVar staging |
| Ingestion date | When a parser wrote normalized rows from that snapshot | Can be later than retrieval if parsing is repeated |
| Guideline effective date | The date the issuer says the recommendation applies, when the document states one | Often absent. Absent stays empty |
| Internal approval date | When a reviewer accepted a GenomIQ rule that cites the snapshot | Empty until a review event says so |
| Internal publication date | When that approved rule became the current published version | A `kb_version` publication, not the download |

A report displays the source release and the retrieval date. It does not display the ingestion date as if it were the publisher’s date.

## Required fields on every snapshot

| Field | Rule |
|---|---|
| `source_id` | Stable identifier, from the registry in document 142 and later additions |
| `publisher_release` | The publisher’s own string. If the publisher has none, `unversioned` and the retrieval date, and the snapshot cannot feed a rule |
| `source_url` | The exact URL fetched, not a website home page |
| `retrieved_at` | Timestamp with timezone |
| `checksum_sha256` | Of the stored bytes. Gzip CRC is not a substitute. ClinVar’s downloader checks gzip integrity and does not store this checksum today |
| `byte_count` | Of the stored object |
| `content_type` | gzip, JSON, XLSX, PDF, OWL, TSV |
| `parser_version` | Git revision or package version of the parser that read it |
| `normalization_version` | Normalizer and FASTA, or `not_applicable` |
| `schema_version` | Internal schema the parsed rows used |
| `transform_version` | The mapping version from document 153 |
| `supersedes` | Previous snapshot id, or empty |
| `effective_date` | Only if the source states one |
| `license_snapshot` | Identifier of the license text that was in force, itself stored |
| `takedown` | Empty, or a privacy or legal withdrawal that blocks redistribution while keeping the checksum record |

The raw object is immutable. A parser bug is fixed by a new `parser_version` reading the same bytes and writing a new parsed generation. The old parsed generation remains.

## Snapshot kinds

| Kind | Unit | Why it is not one row |
|---|---|---|
| File release | The gzip, OWL, or XLSX | ClinVar’s weekly file can change after release if personal data are removed. The checksum distinguishes the copies |
| API extract | The concatenated JSON pages, saved before parsing | A live PostgREST read is not repeatable unless the body is saved. CPIC paging can shift |
| Guideline document | One PDF | The API row that points at it is a different snapshot |
| Ontology | One OBO or OWL release | Reports cite this id |
| License | The license page or file | A later license does not rewrite the old one |

`files.cpicpgx.org/.../current/...` is a moving URL. A snapshot stores the bytes and the `Last-Modified` header. The URL alone is not the version. If a dated archive URL is later found, new snapshots use that URL. Old snapshots keep the URL they used.

## Corrections, withdrawals, and deletions

| Publisher event | GenomIQ action |
|---|---|
| Corrected file, same release name | New snapshot, new checksum, `supersedes` the previous. Both remain. Redistribution uses the newest unless a signed report pinned the old one |
| Privacy takedown | New snapshot with the publisher’s corrected file. The old object is marked `takedown` and is not served to customers. The checksum and the reason remain so an audit can show why a report’s annex changed |
| Record deleted upstream | The parsed row is marked `absent_from_release` at the new snapshot. It is not deleted from the old snapshot |
| Assertion reclassified | A new evidence row. The old classification remains on the old snapshot. Document 154 opens a conflict or a supersession. It does not edit the old text |
| New allele definition | A new allele entity if the definition changed. PharmVar’s own rule, from the partial standards extract, is that a changed haplotype gets a new PharmVar ID and the old ID is retired. Until PharmVar is licensed, CPIC workbook rows follow the same pattern: a changed definition is a new row, not an edit |
| Transcript version changed | The old HGVS stays attached to the old accession version. New annotations use the new version. They are not the same variant description |
| Ontology term replaced | Document 147. Old reports keep the old term |
| Two releases disagree | A conflict record. Neither release is deleted |
| Guideline retired | The new guideline snapshot says it replaces the old one. Signed reports that used the old guideline remain interpretable. New publications do not use the retired guideline unless a reviewer explicitly pins it |

## What the current tables already store

| Table | Present | Missing for this model |
|---|---|---|
| `clinvar_staging` | Variation id, one aggregate significance, row hash, raw JSON, retrieval time | File checksum, archive name, both assemblies, non-pathogenic rows, SCV identity |
| `cpic_guideline` | API id, version integer, URL, PMID, raw JSON, retrieval time | Response checksum, database tag, PDF checksum |
| `cpic_recommendation` | Recommendation id, raw JSON, retrieval time | The guideline version foreign key is not in the SQL read for this pass. The guideline name is a string |
| `kb_version` | Internal publication versions and rollback by writing a new version | Source snapshots. Rollback of a publication does not restore an upstream file |
| `omim_entries` | Fetch time and JSON, if a sync has run | A license snapshot. This specification does not authorize filling the table |

## Reproducing a historical report

A signed report stores the publication version and the snapshot identifiers it used. Reproduction reads those snapshots, not the current files. If a snapshot was later marked `takedown`, reproduction shows the report text that was signed and withholds the withdrawn raw attachment, with a visible note. It does not pretend the source never contained the record, and it does not silently substitute today’s classification.

## Parser and schema changes

A parser change without a new source file still creates a new parsed generation, because the output changed. A schema change creates a new `schema_version`. Old rows are not migrated in place. A migration writes new rows that point at the old ones.

## Recommendation

Implement the snapshot record before adding another source. The existing retrieval timestamps are necessary and not sufficient. The first backfill is a checksum and a release name for the next ClinVar file and the next CPIC response, without changing clinical classifications.
