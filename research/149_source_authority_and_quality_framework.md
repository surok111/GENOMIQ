# 149. Source authority and quality framework

Accessed 23 November 2026. This is a local evaluation framework. It does not rank sources on one scale. A source can be the authority for a frequency and be unfit for a classification. Scores are not stored. The outcome of an evaluation is a role, a list of permitted fields, and a list of prohibited uses.

## Roles

A source may hold more than one role. Each role is granted per data type, not per organization.

| Role | The source may supply | The source may not supply |
|---|---|---|
| Molecular identity reference | Gene ID, symbol, transcript version, assembly, allele definition | A clinical class |
| Population frequency reference | Counts and frequencies in a named callset | Benign or pathogenic |
| Clinical assertion source | A submitter’s or an aggregate assertion, quoted | The laboratory’s class |
| Gene-disease validity source | A validity label for a gene-disease pair | A variant class |
| Pharmacogenomic guideline | Phenotype translation and a recommendation at a named strength | A regulatory mandate |
| Regulatory source | The text of a table or label that was opened | A guideline’s dose |
| Phenotype ontology | Term identifiers and relations for a release | A diagnosis |
| Disease nomenclature | A disease identifier and a crosswalk | Validity or pathogenicity |
| Technical validation resource | Benchmark regions and expected calls | Clinical knowledge |
| Analytical software | Annotations tied to a tool version | A knowledge record without the tool version |
| Research-only source | A note that a reviewer can see and that cannot be published as a rule | A deterministic rule |

## Criteria

Each criterion is recorded as a short factual statement plus the status of that statement: `fetched`, `partial`, `prior_opened`, `failed`, or `not_opened`. An unknown criterion is `unresolved`. It is not a passing mark.

| Criterion | What “acceptable for a rule” requires |
|---|---|
| Authority | A named publisher that maintains the record and can correct it |
| Primary versus secondary | The record is the issuer’s own statement, or it is labeled as a reprint |
| Review process | The issuer states who reviews, or the product is explicitly an unreviewed archive of submissions |
| Completeness | The snapshot says what it omits. A pathogenic-only filter is an internal omission and must be labeled |
| Update cadence | A release, a weekly file, or a stated “no single release” |
| Version transparency | A version, a file name, or a date that can be stored |
| Identifier stability | An identifier that survives a label change, or an explicit warning that it does not |
| Conflict handling | The source keeps disagreeing records, or it aggregates them and says so |
| Accessibility | A documented download or API that this project has actually reached |
| Licensing | The license text was fetched, and it covers the intended storage and redistribution |
| Redistribution | The license allows the intended deployment. Free browsing is not enough |
| Reproducibility | The same version and the same parser produce the same records |
| Deterministic use | A field can be copied without a judgement the source did not make |

A source fails closed. If licensing or identity is `unresolved`, the source can still be read by a person. It cannot feed a published rule.

## Application

The judgements below are interpretations of the evidence in documents 142 through 148. They are not new measurements.

| Source | Strong role | Unfit role | Blocking gap |
|---|---|---|---|
| HGNC | Molecular identity for symbols and HGNC IDs | Clinical class | Download manifest not opened. The about page does state unrestricted use |
| MANE | Transcript identity on GRCh38 | Tissue expression. GRCh37 without the mapping file | FTP README and EBI license not opened |
| NCBI Gene and RefSeq | Accession identity | Interpretation | Release not downloaded. Policy was fetched |
| CPIC guidelines and workbooks | Pharmacogenomic guideline. Function, where a workbook was read | Regulatory label. PharmVar identity | Live license page empty. Workbooks not retained. CC0 text was fetched from Git tag v1.53.1 |
| PharmVar | Intended allele-definition authority | Any current role | Terms page empty. API 401 |
| ClinPGx annotations | Research-only until license review | Guideline | Policy page empty. Extract conflicts with a simple CC BY-SA reading because it also says not for sale |
| FDA associations table | Regulatory source for that table | Label text. CPIC dose | Table is a prior local copy. Website policy was fetched |
| EMA | None yet | Bulk SmPC store | Legal notice fetched. Product copyright not checked |
| DPWG | None as primary | A merged “European” dose | Monograph not opened |
| ClinVar summary | Clinical assertion, aggregate, quoted | Laboratory class. Frequency. Complete conflict record | Ingest drops non-pathogenic rows and one assembly |
| ClinVar SCV XML | The missing submitter layer | Not yet used | File not downloaded |
| gnomAD | Frequency | Classification. SpliceAI redistribution | Policy fetched. Data file not opened |
| dbSNP | Identifier | Class. Frequency | Build not re-downloaded |
| ClinGen validity | Gene-disease validity | Variant class | Terms fetched. Data file not opened |
| GenCC | A second validity submission set | A vote | Terms fetched. File not opened |
| OMIM | None for publication | Validity class. Redistributed narrative | Agreement fetch failed |
| Orphadata Science | Disease nomenclature | Validity | FAQ fetched. XML not downloaded |
| HPO | Phenotype ontology, once licensed | Diagnosis | License page not opened |
| MONDO | Disease crosswalk | OMIM text | Foundry record fetched. OWL not downloaded |
| SNOMED | None | Embedded terminology | License not opened |
| GeneReviews | A cited chapter that was opened | Bulk text | Bookshelf notice not opened |
| PanelApp | None | Diagnostic panel | 2019 terms only, and those restrict diagnostic use |
| DECIPHER | None | Patient archive | Agreement not opened |
| HGMD | None | Any role | HTTP 403 |
| LOVD, BRAVO, dbVar, GIAB, UniProt, Ensembl bulk, UCSC | None yet | A silent extra feed | Not opened or the fetch failed |
| `KNOWN_VARIANTS` | None | Allele reference | No provenance |

## What the framework refuses

A numeric authority score. A rule that “the newest source wins.” A rule that a CC0 source is clinically correct. A rule that an NIH-funded source may be resold without reading its terms. ClinPGx is the example: the policy page did not load, and the extract contains both a Creative Commons license and a no-sale clause. Until counsel reads the page, the framework’s licensing criterion is `unresolved`.

Primary evidence outranks a reprint of the same evidence. The Medical Genetics Summary reprint of a DPWG table does not outrank, and does not replace, the unread DPWG monograph. It also does not outrank a CPIC PDF that was opened. They are different statements.

An archive of submissions, which is what ClinVar is, has a different authority from a curated validity classification, which is what ClinGen gene-disease validity is. Both can be right to use. They answer different questions.
