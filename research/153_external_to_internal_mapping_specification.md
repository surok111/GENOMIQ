# 153. External-to-internal mapping specification

Accessed 23 November 2026. This is a conceptual mapping. It is not a database migration and not an importer. An imported assertion remains an external assertion. It becomes internal knowledge only when a review decision says so.

## The chain

Every prioritized source follows the same chain. A stage that has no input stays empty. It is not filled from a neighboring stage.

1. External source record, as the publisher defines it.
2. Raw immutable artifact, the snapshot in document 152.
3. Parsed source record, one row per publisher record, still in the publisher’s field names.
4. Normalized external entity, identifiers and values converted under a named transform, still attributed to the source.
5. Internal molecular or clinical entity, a GenomIQ object such as a gene, transcript, allele, or drug. It may exist before any source is linked.
6. Evidence claim, a checkable statement that cites the normalized record.
7. Review decision, a person’s disposition. Pending is the default.
8. Versioned internal knowledge, a published claim or an explicitly informational record.
9. Published deterministic rule, only if the claim’s role is a rule and the review approved it. Otherwise the chain stops at an informational record.

Document 79’s Claim, Source, Evidence, ClaimEvidence, Conflict, and ReviewEvent are the objects this chain uses. This document adds the raw artifact and the normalized external entity, which document 79 left inside “source.”

## What must stay distinguishable

| Layer | Example | Forbidden collapse |
|---|---|---|
| Publisher aggregate | ClinVar `ClinicalSignificance` = Conflicting interpretations | Storing it as GenomIQ `uncertain` |
| Publisher recommendation | CPIC Strong, avoid this drug | Storing it as a local dose calculator with no guideline version |
| Publisher frequency | gnomAD v4.1 allele count | Storing it as “rare” or as benign |
| Publisher validity | ClinGen Limited | Storing it as “not a real gene” |
| Internal rule | A reviewer-approved phenotype bin | Overwriting it when the next CPIC file arrives |

The internal entity and the external record are linked. They are not the same row.

## Identity keys

| External identifier | Internal identifier | Cross-reference |
|---|---|---|
| HGNC ID | Internal gene id | Symbol and NCBI GeneID are properties, versioned |
| NCBI GeneID | The same internal gene | Only when the snapshot says they correspond |
| MANE transcript pair | Internal transcript id | RefSeq version and Ensembl version are both stored |
| ClinVar VariationID plus assembly plus allele | Internal variant id | Right-shifted and left-aligned coordinates are two representations |
| ClinVar SCV | External assertion id, not a variant id | Many SCVs can point at one variant |
| rs identifier | Cross-reference only | Not unique enough to be the variant id |
| CPIC guideline id and version | External guideline id | Not an internal rule id |
| CPIC recommendation id | External recommendation id | Drug, phenotype, and strength stay on this record |
| CPIC workbook allele name plus gene plus workbook snapshot | External allele definition | Not a PharmVar ID |
| PharmVar ID, when licensed | External allele id | Star name is a label |
| gnomAD variant key plus release | External frequency observation | Not a variant class |
| ClinGen gene-disease curation id | External validity assertion | Not a variant assertion |
| GenCC submission | A separate validity assertion | Not merged into the ClinGen row |
| HPO id plus release | External term | Patient observations point at the term and do not become the ontology |
| Mondo id plus release | External disease | OMIM and Orphanet numbers are cross-references |
| FDA table row plus snapshot date | External regulatory statement | Not a CPIC recommendation |

Internal identifiers are opaque and stable. They are not the publisher’s identifier, because the publisher can retire or reuse a label. The cross-reference table holds the publisher identifier, the snapshot, and the match method.

## Source-specific fields that survive normalization

Normalization copies a field into a shared column only when the meaning matches. Everything else stays in a source-specific structure on the parsed record.

| Source | Shared columns | Fields that stay source-specific |
|---|---|---|
| ClinVar summary | Assembly, chromosome accession, start, stop, ref, alt, gene symbols, aggregate significance, review status, last evaluated | `ClinSigSimple`, submitter count, GTR flag, the old ACMG incidental-findings column, truncated phenotype counts |
| ClinVar SCV, when added | Assertion, condition, submitter, date | The submitter’s free text and method, unmodified |
| CPIC recommendation | Drug, phenotype key, strength, guideline version | The recommendation sentence, unmodified |
| CPIC workbook | Gene, allele name, activity value, clinical function | The workbook’s own strength spelling, including the `Definitve` cell document 31 recorded |
| gnomAD | AC, AN, homozygote count, filtering allele frequency, ancestry group | Flags such as exome-genome discordance. SpliceAI is not copied into the shared record |
| ClinGen | Gene, disease, validity label, release | SOP version and curator notes |
| HPO | Term id, label, parents, obsolete flag | Annotation frequency on a disease file, which is a different artifact |

## Original text

The recommendation sentence, the assertion string, the validity label, and the regulatory sentence are stored as the publisher wrote them, with the snapshot id. A paraphrase in a report is a separate field and cannot replace the original. Whitespace normalization is allowed only if the original bytes remain in the raw artifact.

## Unmapped and duplicate records

An unmapped field is retained on the parsed record and listed in a transform report. It is not discarded and not given a guessed meaning.

Duplicate detection keys:

| Source | Duplicate | Not a duplicate |
|---|---|---|
| ClinVar | Same VariationID, same assembly, same allele, same snapshot | The GRCh37 row and the GRCh38 row |
| ClinVar assertions | Same SCV | Two SCVs with the same class and different submitters |
| CPIC | Same recommendation id | Two drugs in one guideline |
| Alleles | Same gene, same variant set, same snapshot | The same star name with a different variant set |
| Frequencies | Same variant key, same release, same population | Exome count and genome count |
| Validity | Same submitter, same gene, same disease, same release | ClinGen and GenCC rows for the same gene |

When two non-duplicate records disagree, the loader writes both and opens the conflict type in document 154. It does not keep the newer timestamp.

## Supersession

A new snapshot can mark a parsed record as superseded. Supersession links the new record to the old one and records the reason: publisher correction, reclassification, identifier retirement, or parser fix. The old record remains queryable. Internal knowledge that cited it is sent to the impact process in document 156. It is not edited.

## Worked paths

ClinVar. The gzip is the artifact. A TSV row is the parsed record. The normalized entity has both the right-shifted coordinates and, after a normalizer runs, a left-aligned key. The internal variant is linked, not replaced. The aggregate significance is an evidence claim of type `external_assertion`. Review status is a property of that claim. No review decision is created automatically. Publication of a GenomIQ class does not happen.

CPIC. The saved API body is the artifact. One recommendation is the parsed record. The normalized entity has drug, phenotype, and strength. The sentence is an evidence claim of type `guideline_recommendation`. A deterministic rule is created only after approval. The existing ingest already stops in staging and the review queue. This mapping says that stop is the correct one.

gnomAD. A release file is the artifact. A frequency observation is not an evidence claim of pathogenicity. It can be cited by a frequency comparison in document 92. The comparison’s parameters are GenomIQ inputs, not gnomAD fields.

## Recommendation

Add the raw artifact and the normalized external entity to the conceptual model before writing another importer. Keep publisher field names until a transform version maps them. Do not point a published rule directly at a live API.
