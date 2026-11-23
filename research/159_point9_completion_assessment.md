# 159. Point 9 completion assessment

Accessed 23 November 2026. Point 9 asked which external sources can support a deterministic, traceable knowledge base, and under what license and version rules. The answer is in documents 142 through 158. No integration was built.

## Counts

The inventory in documents 142 through 148 names 52 sources or source-like objects. That count includes code paths, prior research objects, pages fetched this pass, failed fetches, and named resources that were deliberately not opened. It is not a count of approved dependencies.

| Group | Count | How it was counted |
|---|---|---|
| Sources and source-like objects discussed | 52 | The union of the inventory, the variant and pharmacogenomic audits, the identity and disease audits, and the explicitly not-opened list |
| Publisher pages or files that returned readable text this pass | 14 | NCBI policy, ClinVar README, CPIC `LICENSE.md` at tag v1.53.1, ClinPGx API landing, gnomAD policies, ClinGen terms, GenCC terms, Orphadata FAQ, MANE page, HGNC about page, MONDO OBO Foundry record, HPO README, FDA website policy, EMA legal notice |
| Official URLs that returned an empty body | 4 | PharmVar terms, PharmVar documentation, `cpicpgx.org/license/`, ClinPGx data-usage policy |
| HTTP failures or a page that was not the requested terms | 6 | OMIM agreement 403, HGMD 403, IPD terms 404, Ensembl disclaimer timeout, UniProt license fallback, DECIPHER data-sharing URL returning a search-help page |
| Working programmatic clients already in the repository | 4 | CPIC PostgREST, ClinVar FTP, ClinPGx REST, NCBI E-utilities. OMIM’s official API is coded and was not called. PharmVar’s API returned 401 in a prior session |
| Version schemes described on a page that was read | 5 | ClinVar weekly file and monthly archive. MANE v1.5 and roughly yearly updates. gnomAD v4.1 dated 19 April 2024 on the policies page. Orphadata Science XML in June and December. CPIC’s license file says API downloads are cited with a version number. The local client stores a guideline version integer. HPO and MONDO release tags were not checked out. HGNC ID stability is identifier stability, not a release cadence |
| Licenses confirmed from a fetched publisher text | 10 | CPIC GitHub license, ClinGen terms, GenCC terms, gnomAD policies, HGNC about page, FDA website policy, EMA legal notice, Orphadata FAQ, MONDO Foundry record, NCBI molecular-data policy |
| Licenses unresolved | 14 | ClinPGx full policy, CPIC live license page, PharmVar, OMIM, IPD-IMGT/HLA, Ensembl, UniProt, HPO, GeneReviews notice, PanelApp current terms, DECIPHER, HGMD, SNOMED, DPWG/KNMP |

Versioning “confirmed” means the publisher described a release scheme or a fetched page named a version. It does not mean a data file was downloaded in this pass. gnomAD, MANE, ClinGen, GenCC, HPO, and MONDO files were not downloaded.

## Already used by GenomIQ

In code: CPIC API, ClinVar variant summary, ClinPGx API, OMIM API with an NCBI fallback, ClinVar E-utilities, a static `KNOWN_VARIANTS` map, and ORCID for authors.

On disk from 23 November 2026 research: CPIC JSON extracts and the FDA associations table. CPIC workbooks were read earlier and were not retained. Guideline PDFs were read earlier and were not retained.

None of these is a complete, checksummed, historical source archive.

## Highest-priority missing sources

For pharmacogenomics: retained CPIC workbook snapshots, a readable copy of the live CPIC license page, and the FDA table kept beside CPIC rather than merged with it. PharmVar is the correct missing allele authority and is blocked on a terms page that did not return text.

For a WES/WGS review aid: a reference FASTA, a MANE file, an HGNC file, a ClinVar archive that keeps every significance and both assemblies, a gnomAD release without SpliceAI, and a ClinGen validity file. HPO is scientifically next and legally blocked until its license page is opened.

## Reusable components

The ClinVar downloader, the CPIC client, the staging tables, the review-queue rule that clinical changes stay pending, the publication and rollback functions, and the PostgreSQL backup path can be reused as transports and as gates. They are not a source registry, not an immutable archive, and not a conflict store. The ClinVar parser’s pathogenic-only, GRCh38-only behavior is the main defect. The gene-store OMIM and ClinPGx sync bypasses the review queue and is not reused for publication.

## Architectural changes required before more sources are added

1. A source registry with a license snapshot and an allowed-use flag.
2. Content-addressed raw files and a snapshot row with a release name and SHA-256.
3. ClinVar storage that keeps the rows and assemblies the current parser drops, and a hash that includes condition and `ClinSigSimple`.
4. Saved CPIC response bodies, not only upserted rows.
5. Separation of the SQLite gene store from anything that could ship OMIM text.
6. Conflict records for the cases in document 154.
7. Publication rows that cite snapshot ids, so document 156’s impact walk has somewhere to start.

No new server is required. Document 158 is a directory plus the PostgreSQL instance the project already uses.

## Conflict types

Issuer against issuer, aggregate against its parts, definition change, assembly and transcript scope, secondary reprint against a primary text, frequency against classification, and validity label against a different submitter’s validity label. The model does not let the newest date or a star rating choose.

## Highest-risk dependencies

| Risk | Why |
|---|---|
| OMIM text in the gene-store schema | The agreement page returned 403, and the extract that was seen forbids transfer and requires a commercial license |
| ClinPGx annotations | The policy page did not load, and the extract mixes CC BY-SA with a no-sale clause |
| PharmVar | Allele truth for several genes, and no readable license or successful API call |
| ClinVar ingest filter | The system can look as if it ingested ClinVar while it dropped conflicts and benign assertions |
| `KNOWN_VARIANTS` | Alleles with no source and no build |
| gnomAD SpliceAI columns | Restricted, inside an otherwise CC0 release |
| Floating `current` CPIC workbooks and floating ClinVar URL | A later run can replace history without a version |
| DPWG reprints | A secondary table can be mistaken for the monograph |

## Tier 1 sets

Pharmacogenomics: CPIC guideline snapshots, CPIC workbook snapshots, HGNC, and the dated FDA associations table.

WES/WGS review aid, if that product is authorized: GRCh38 FASTA, MANE, HGNC, full ClinVar monthly archive, gnomAD frequency file without restricted annotations, and ClinGen gene-validity. HPO is the next phenotype source and is not tier-1-cleared until its license page is read.

## Implementation sequence, when implementation is separately authorized

1. Registry, snapshot row, and raw directory. No new clinical content.
2. Point the existing ClinVar and CPIC jobs at that directory and stop discarding ClinVar classes.
3. Pin HGNC and MANE for identity. Retire dependence on `KNOWN_VARIANTS` only by linking each allele to a workbook row, not by inventing definitions.
4. Counsel review of ClinPGx, OMIM, PharmVar, HPO, and any plan to ship ClinVar free text.
5. gnomAD frequency snapshot with restricted annotations excluded.
6. ClinGen validity file, then GenCC as a comparison.
7. HPO and MONDO only after their file headers and the HPO license page are read.
8. Leave DPWG, EMA labels, PanelApp, DECIPHER, HGMD, and OMIM narrative unimplemented.

## Confirmation

No file under `src/`, `data/`, `reports/`, or a database was modified. No parser, staging table, knowledge-base record, or clinical classification was changed. No source was downloaded into the project. No server was provisioned. No license was purchased. No restricted dataset was redistributed. The only files created are the eighteen research documents named in the task, including this assessment.
