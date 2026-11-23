# 146. Gene-disease and clinical-validity sources

Accessed 23 November 2026. A gene-disease association is not a variant classification. A variant classification is not a diagnosis. A phenotype list is not a management recommendation. Each source below is assigned only the layer its retrieved terms support.

## ClinGen

Terms page fetched: `https://www.clinicalgenome.org/docs/terms-of-use/`.

The page says curated content, and it names gene-disease validity, dosage sensitivity, and clinical actionability, is under CC0 1.0. It requests attribution and the date accessed. It says the logo needs steering-committee approval. It points to a separate Variant Curation Interface user agreement, which was not opened. The page displays the date 26 January 2018. The same page cites a 2024 consortium paper. The visible date is not proof that no later terms exist. The CC0 sentence is what was read.

The bulk download, the API, and a current curation release were not opened. No endpoint is invented. Document 98 already cites the 2017 validity classes and notes that a later SOP splits disputed and refuted evidence. That SOP was not downloaded.

What ClinGen can be, once a release file is pinned:

| Layer | Use the curation for | Do not use it for |
|---|---|---|
| Gene-disease validity | Definitive, strong, moderate, limited, and the conflict or refuted labels the pinned SOP actually uses | Pathogenicity of one variant |
| Dosage sensitivity | A haploinsufficiency or triplosensitivity score, labeled as dosage | A small-variant class |
| Clinical actionability | An actionability curation, if that file is the one retrieved | A secondary-findings list. ACMG SF is a different product |
| Variant curation expert panels | A specification a reviewer reads | An automatic criterion engine. Document 98 already refuses that |

Recommended role: gene-disease validity source, and dosage source when that file is snapshotted. Not a variant-pathogenicity feed by itself. Expert-panel variant specifications stay human-readable references.

## GenCC

Terms fetched: `https://thegencc.org/terms`.

The page says GenCC data are under CC0 1.0 and asks for attribution to GenCC and to the contributing sources. The flagship citation is given as a Genetics in Medicine article. The download file and the list of submitters in the current release were not opened.

GenCC collects gene-disease validity submissions from several groups. A Definitive submission from one group and a Limited or disputed submission from another are a conflict, not a vote. The GenCC record is not the OMIM narrative and does not waive OMIM’s license. Store the submitted classification, the submitter, the disease identifier, and the GenCC release. Do not copy a contributor’s prose through GenCC.

Recommended role: a second validity source used to show agreement and disagreement with ClinGen. Not a replacement for ClinGen and not a diagnosis.

## OMIM

The code calls `https://api.omim.org/api` when a key is present, and otherwise uses NCBI E-utilities. A direct fetch of `https://www.omim.org/help/agreement` returned HTTP 403. A search extract of that URL and of `https://www.omim.org/downloads/` included these clauses: the agreement binds website, API, and download users; data are for research and education and are not a substitute for the literature or for medical consultation; Johns Hopkins holds the copyright; commercial download requires a paid license; the license is non-exclusive, non-transferable, and non-sublicensable; users may not sell or transfer the data; a database that uses a download must be refreshed at least weekly; `mim2gene.txt` is available without registration; other files require registration, and for-profit redisplay requires a license. The full agreement was not retrieved. Clauses after the ones in that extract are unverified. Legal review is required before any download, and the existing SQLite tables must not be treated as a cleared cache.

NCBI’s policy page, which did load, lists OMIM among resources that incorporate copyrighted material and tells users to follow the copyright holder’s terms.

What OMIM contains, as a product, is a curated narrative: gene-phenotype relationships, inheritance, allelic-variant paragraphs, and references. Those paragraphs are not ClinGen validity classes and not ACMG variant classes. An allelic-variant entry is a literature summary. It can be wrong, withdrawn, or limited to a genotype-phenotype observation.

Recommended role: no bulk use and no redistribution until counsel reads the current agreement and a license, if one is required, is in hand. A MIM number already printed in a public crosswalk may be stored as an identifier. The OMIM text may not.

## Orphanet and Orphadata

The Orphadata FAQ `https://www.orphadata.com/faq/` was fetched.

Orphadata Science datasets and APIs that the site marks as such are under CC BY 4.0. The FAQ says commercial use is allowed with credit, that changes must be indicated, and that users may not add restrictions that the license forbids. Orphadata Products require a data-transfer agreement or a service contract. Logos need approval. An AI or service statement is required if the CC BY data are used in a tool offered to third parties. The FAQ says the free XML extracts are produced twice a year, in June and December. It says an API exists and tells the user to make contact. No public base URL was printed. None is claimed here.

The FAQ also says the gene file links genes at the subtype or disorder level and that a parent disorder may not appear in the gene file. Inclusion is a technical choice, not an evidence grade. Orphanet is therefore a nomenclature and a phenotype-disease resource. It is not a validity class.

Recommended role: disease nomenclature and rare-disease crosswalk, from the Science files only, with the data version in the citation the FAQ specifies. Not a variant database. Not the Products collection.

## GeneReviews

Document 74 records one opened chapter, hemochromatosis NBK1440. NCBI’s policy page says Bookshelf has its own copyright notice. That notice was not opened this pass.

GeneReviews is an expert narrative: diagnosis, management, inheritance, and molecular information for a condition. One chapter does not license the series. Recommended role: a cited reference for claims that quote a retrieved chapter. Not a bulk knowledge base. Not a variant classification.

## PanelApp

A search extract of the Genomics England PanelApp terms PDF dated December 2019 includes a prohibition on commercial use and on diagnostic or healthcare use unless a separate agreement exists, an acknowledgement requirement, and sublicence clauses for OMIM and Orphanet. The current website terms were not fetched, so it is not known whether December 2019 is still the live text. Status: `partial`.

PanelApp rates gene panels for a condition. A green rating is a panel-inclusion decision. It is not ClinGen validity and not a variant class. Recommended role: none until the current terms are read and a use is inside them. Diagnostic use is specifically the use this product would make, and the 2019 extract restricts that use.

## DECIPHER

`https://www.deciphergenomics.org/about/data-sharing` returned a search-help page for DECIPHER v11.43, not a data-sharing agreement. The page shows that the browser can query by phenotype, GRCh37 or GRCh38 position, gene, and consequence. It does not state a license. Status: the agreement was `not_opened`.

DECIPHER deposits include patient-level and variant-level observations. Even a public browser is not permission to copy a cohort into a customer deployment. Recommended role: none. Do not ingest patient-level records.

## Other resources

GenCC’s contributors include groups whose own sites were not licensed here. Going to those sites is a different source. The Monarch Initiative and Orphanet disease pages can repeat one another. Repetition is not independent evidence.

## Layer matrix

| Source | Validity | Variant pathogenicity | Diagnosis | Phenotype | Inheritance | Mechanism | Management |
|---|---|---|---|---|---|---|---|
| ClinGen validity | Yes, when the release is pinned | No | No | Often linked, not a full HPO set | Often stated | Sometimes | No |
| ClinGen dosage | A dosage score | No | No | No | No | Dosage mechanism only | No |
| GenCC | Submitter-level validity | No | No | Disease name only | As the submitter recorded it | No | No |
| OMIM | Not as a ClinGen class | Narrative only, and not licensed | No | Yes, narrative | Yes, narrative | Sometimes | Sometimes, narrative |
| Orphanet Science | No | No | No | Disease nomenclature | Sometimes in the classification files, which were not downloaded | No | No |
| GeneReviews | No | Narrative in a retrieved chapter | No | Yes | Yes | Sometimes | Yes, in that chapter |
| PanelApp | A panel rating, terms unresolved | No | No | Panel name | No | No | No |
| DECIPHER | No | Patient-derived observations, terms unread | No | Yes | Sometimes | No | No |
| ClinVar | No | Aggregate or SCV assertion | No | Condition identifiers | No | No | The README’s guideline column is an old ACMG incidental-findings flag, not current management |

## Recommendation

For a WES/WGS review aid, pin a ClinGen validity release and, as a comparison, a GenCC release. Both are CC0 on the pages that were read. Keep Orphanet as a disease identifier under CC BY, from Science files only. Leave OMIM text, PanelApp, DECIPHER, and GeneReviews out of the distributable database until their own terms are read and accepted. Do not promote a gene-disease row into a variant classification.
