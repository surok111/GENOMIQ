# 142. Existing external source inventory

Accessed 23 November 2026. This inventory is what the repository and the earlier research documents actually contain. A mention in a prior document is not treated as a new verification. Status words are defined below. No production file was changed while this inventory was written.

## Status words

| Status | Meaning |
|---|---|
| `code` | The repository contains a client, URL, or static table. This pass did not call the service |
| `local_file` | A file under `research/sources/` or `data/` was produced by an earlier retrieval |
| `prior_opened` | A numbered research document records that a page or file was opened. This pass did not reopen it |
| `fetched` | This pass retrieved the page body |
| `partial` | An official URL returned an extract or an empty script shell. The full terms were not read |
| `failed` | This pass or a recorded earlier request returned an HTTP error or an empty body |
| `not_opened` | The source is named because the project needs it or a publisher page names it. No terms and no payload were read |

A source can have more than one status. `code` plus `failed` means the client exists and a content request did not succeed.

## What the running code actually calls

These are the only external genetic sources with an implementation in `src/`. ORCID is listed because the code calls it. It is not a genetic knowledge source.

| ID | Source | Where | What the code does | What it does not do |
|---|---|---|---|---|
| SRC-CPIC-API | CPIC PostgREST at `https://api.cpicpgx.org/v1/` | `src/cpic_ingest/client.py` | GET `guideline` with publication fields, and `recommendation_view` by drug name. Range pages of 1000. Retries transport errors, HTTP 429, and HTTP 5xx. User-Agent `GENOMIQ/1.0 (cpic-ingest)` | Does not download allele-definition workbooks. Does not read guideline PDFs. Does not publish into the clinical knowledge base |
| SRC-CLINVAR-FTP | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz` | `src/clinvar_ingest/download.py` | Streams the gzip, resumes with HTTP Range, checks the gzip CRC | Does not store the ClinVar release date. Does not download the XML or the submission-level file |
| SRC-CLINVAR-PARSE | The same summary, after download | `src/clinvar_ingest/parser.py`, `schema.py`, `hashing.py` | Keeps a row only when `ClinicalSignificance` is exactly `Pathogenic` or `Likely pathogenic`, and a gene symbol matches the local knowledge base. Collapses the two assembly rows to one `VariationID`, preferring GRCh38. Hashes a subset of columns | Drops VUS, benign, conflicting, and risk assertions. Drops the GRCh37 coordinate once GRCh38 is seen. Does not store each submitter |
| SRC-CLINPGX-API | `https://api.clinpgx.org/v1/data` | `src/genedb/clients/clinpgx.py` | Gene by symbol and up to 80 clinical annotations. The client waits at least 0.55 s between calls | The code comment says the former PharmGKB API and a limit of 2 requests per second. This pass did not re-measure the limit. The API landing page, fetched this pass, states 2 per second |
| SRC-OMIM | `https://api.omim.org/api`, with a fallback to NCBI E-utilities | `src/genedb/clients/omim.py`, `src/genedb/store.py` | If `OMIM_API_KEY` is set, searches by approved gene symbol and requests gene map, allelic variants, and flags. Otherwise uses NCBI. SQLite tables `omim_entries` can store title, phenotypes, and allelic-variant JSON | This pass did not call the API. The use agreement page returned HTTP 403. Storing OMIM text is not an approved redistribution |
| SRC-CLINVAR-EUTILS | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` | `src/genedb/clients/clinvar.py` | ESearch and ESummary for a gene, with counts for pathogenic, likely pathogenic, VUS, likely benign, and benign. Keeps up to 120 variation records in the gene store | A second ClinVar path, separate from the FTP ingest. It does not replace the FTP snapshot |
| SRC-NCBI-EUTILS | The same E-utilities host | OMIM fallback and the dbSNP calls recorded in document 31 | Document 31 records an `esummary` call for named rs identifiers on 23 November 2026 | That call did not return coordinates or a chosen transcript |
| SRC-ORCID | `https://pub.orcid.org/v3.0/` | `src/orcid_search.py` | Author lookup | Out of scope for genetic knowledge |

Prefect flows in `src/orchestration/flows.py` schedule `clinvar-ingest` at 02:00 UTC on Tuesday and `cpic-ingest` at 03:00 UTC daily. Both flows call the ingest functions and return. They do not approve or publish. The review-queue policy in `src/review_queue/policy.py` leaves clinical changes, recommendation text, evidence level, and conflicts in `pending`. `auto_accepted` is explicitly not publication.

`src/kb_version/publish.py` can publish one approved change or roll back to an older version by writing a new version. It is a version mechanism for internal entities. It is not a source-snapshot store.

`src/interpreter.py` contains `KNOWN_VARIANTS`, a static map from rs identifier to a reference and alternate allele. The map has no source, no build, no transcript, and no retrieval date. Document 26 already says this map is not a molecular foundation. It is an embedded source with unknown provenance.

## Files already on disk

| Path | What it is | Retrieval recorded | Version recorded |
|---|---|---|---|
| `research/sources/cpic_guidelines.json` | CPIC guideline list from the API | 23 November 2026, research README | Guideline version is inside rows when the API sent it. The file itself has no separate checksum in the research README |
| `research/sources/cpic_drugs.json` | CPIC drug list | Same date | Not a release identifier |
| `research/sources/cpic_genes.json` | CPIC gene list | Same date | Same |
| `research/sources/cpic_pairs_panel.json` | Actionable gene-drug pairs | Same date | Same |
| `research/sources/cpic_recommendations_panel.json` | Recommendation rows for the local panel | Same date. Document 20 says the carbamazepine phenotype objects in this extract are empty | Not the guideline PDF |
| `research/sources/cpic_recommendations_unique.json` | Deduplicated recommendations | Same date. The research ledger says the tricyclic guideline stopped at a 500-row page and warfarin guideline id 100425 returned no rows | Incomplete relative to the live API |
| `research/sources/cpic_warfarin_recs.json` | Warfarin recommendation extract | Same date | The empty-result fact is in the ledger |
| `research/sources/fda_pgx_associations_2026-11-23.md` | FDA Table of Pharmacogenetic Associations copied into markdown | 23 November 2026 | The FDA page date is not a structured version field in that markdown |
| `data/group*.txt` | Local knowledge-base text | Local. Document 74 calls this S25, a local claim source, not external evidence | No external version |

CPIC allele-definition and allele-function workbooks were downloaded during the work recorded in document 31. They are not in `research/sources/` now. Their Last-Modified time was recorded as 26 October 2026 for the workbooks that returned HTTP 200. CYP1A1 and CYP1A2 definition files returned HTTP 404. Those workbooks are `prior_opened`, not a current local archive.

## Sources used by research conclusions and not in the provenance model

Document 79 proposes a provenance model. It is not implemented. Document 74 is a claim-level registry, S01 through S26. The rows below are external objects that research used and that the proposed model does not yet store as versioned artifacts.

| ID | Object | How it was used | Gap |
|---|---|---|---|
| SRC-CPIC-PDF | Individual CPIC PDFs on `files.cpicpgx.org`, including PMID 35034351 and the 2017 warfarin PDF | Phenotype bins and recommendation boundaries in documents 20, 45, 49, 60, and 74 | The PDF bytes and checksum are not in the repository. Some rows in document 74 are “prior extract” or “summary,” not a re-opened PDF |
| SRC-CPIC-XLSX | Allele-definition and allele-function workbooks | Molecular identity in documents 29 through 36 | Files not retained. PharmVar was not the source of those rows |
| SRC-PHARMVAR | `https://www.pharmvar.org/` and `https://www.pharmvar.org/api-service/genes` | Document 31: HTML shells of about 1.5 KB and HTTP 401, “API Key is invalid or missing” | No allele grid. A 401 is not an empty catalog |
| SRC-PHARMVAR-PDF | CYP2D6 Read Me and Variation PDFs under `/gene-support/` | Documents 33, 34, and 42. Legacy `htdocs` pages were marked historical | PDFs not retained here. The terms page was not the thing that was read |
| SRC-FDA-TABLE | FDA Table of Pharmacogenetic Associations | Local markdown above. Document 74 says FDA label PDFs named in group 5 were not opened | The table is not a label, and a local “FDA” cell is not a regulatory statement |
| SRC-DPWG | DPWG recommendations | Document 74 S11 is a 2019 journal table. S23 is a Medical Genetics Summary reprint titled DPWG 2025. The KNMP monograph was not opened. A ClinPGx filter `source=dpwg` returned HTTP 400 | Secondary text is not the DPWG primary |
| SRC-IPD | IPD-IMGT/HLA release 3.66.0, dated 2026-10-14 in document 74 | Four named alleles retrieved in the HLA task. A later allele-page request did not contain the expected string | Not a complete HLA source. Terms URL returned HTTP 404 this pass |
| SRC-DBSNP | dbSNP build 157 pages and E-utilities summaries | Document 74 S18 and document 31. Build date 3 September 2024 was on the pages that said so | Not every local rs was opened. The summary’s blended clinical string was not used as function |
| SRC-GENE-REVIEWS | GeneReviews hemochromatosis, NBK1440 | Document 74 S15, full-text extract | One chapter. Bookshelf copyright was not re-read |
| SRC-ACMG-2013 | ACMG MTHFR statement, Genetics in Medicine 2013 | Document 74 S16 | One statement. Not a general ACMG subscription |
| SRC-MGS | NCBI Medical Genetics Summaries, including lecanemab/APOE and a warfarin DPWG reprint | Documents 74 S17 and S23 | Explicitly secondary when the summary reprints another body |
| SRC-CLINGEN-ALLELE | ClinGen allele CA9820806 | Document 74 S22, one HGVS string | Not the ClinGen gene-validity bulk release |
| SRC-CLINPGX-BLOG | ClinPGx blog, 9 July 2026, on a pending DPYD update | Document 74 S10 | An expert note. Not a guideline |

## Sources named and not retrieved

Document 74 and the research ledger already list these as unread. This pass did not close them.

- EMA product-information pages, gene by gene.
- PharmVar’s current allele grid.
- DPWG monograph PDFs from KNMP.
- The CPIC warfarin recommendation body that the API returned empty.
- Full-text PDFs for guidelines that document 74 marks as local quotation only, including carbamazepine PMID 29392710.
- gnomAD frequency tables. The gnomAD policies page was fetched this pass. The data files were not.
- A current ClinGen gene-validity release. The terms page was fetched. The data file was not.
- HPO, MONDO, Orphanet, GenCC, and PanelApp as data files. Terms or descriptions for some of them were fetched and are in documents 146 and 147. The ontology bytes were not.

## Version and date gaps in the current stores

| Store | Date it has | Date it lacks |
|---|---|---|
| `clinvar_staging.source_retrieved_at` | Ingestion timestamp | ClinVar weekly or monthly release identifier. File checksum. The README, fetched this pass, says `variant_summary.txt` is generated weekly and archived monthly |
| `cpic_guideline.version` | The integer the API returned for that guideline | A checksum of the response. The guideline PDF version. An approval date inside GenomIQ |
| `cpic_recommendation.source_retrieved_at` | Ingestion timestamp | The CPIC database release tag. Git tag `v1.53.1` on `cpicpgx/cpic-data` was read for the license file only. It was not shown to be the release inside the local JSON |
| `omim_entries.fetched_at` | Fetch time, if a sync has been run | This pass did not inspect a populated SQLite file and does not claim one exists |
| `KNOWN_VARIANTS` | None | Source, build, transcript, retrieval date |
| Research JSON | The research README’s access date, 23 November 2026 | A checksum. Document 11 may contain baseline checksums for an earlier inventory. Those checksums were not re-verified against the files in this pass |

## Recommended role, before the later documents add conditions

These roles are a starting assignment. Documents 149 and 151 can narrow them. None of these sources is approved internal knowledge merely because it was ingested.

| Source | Role that is justified by current use | Role that is not justified |
|---|---|---|
| CPIC API and the PDFs that were actually read | Pharmacogenomic guideline and phenotype translation, cited at a named table | A substitute for PharmVar allele definition. A dosing rule that was not in the retrieved table |
| CPIC workbooks that were opened | Allele definition and function for the genes and alleles that were read | A complete allele catalog. A current file, because the workbooks were not retained |
| ClinVar FTP ingest | A filtered list of aggregate pathogenic and likely pathogenic assertions for local gene symbols | A full assertion archive. A laboratory classification. A conflict record |
| ClinPGx API | A clinical-annotation index, if the license in document 151 is accepted | A CPIC guideline. A DPWG monograph |
| OMIM client | A pointer to a MIM number after a license is in place | A gene-disease validity class. A variant classification. A redistributable narrative |
| FDA table | A regulatory association table, separate from a label | A CPIC recommendation |
| `KNOWN_VARIANTS` | Nothing, until each allele is replaced by a sourced definition | A reference allele |
| Local `data/group*.txt` | The current internal claim text | An external source |

## What this inventory refuses to count

A URL printed in a comment is not a retrieved dataset. An HTTP 401 is not a negative finding about the biology. An aggregate ClinVar string is not the set of submissions that produced it. A Medical Genetics Summary that reprints DPWG is not DPWG.
