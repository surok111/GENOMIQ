# 150. API, download, and access mechanisms

Accessed 23 November 2026. An endpoint is listed only if the repository calls it, a fetched page names it, or a prior research document records a response code. Pages that returned an empty script shell are not described as working APIs.

## Mechanisms that were actually observed

| Source | Mechanism | Evidence | Authentication | Limits observed | Release identity | Checksum | Incremental update |
|---|---|---|---|---|---|---|---|
| CPIC | HTTPS JSON, PostgREST | `src/cpic_ingest/client.py` uses `https://api.cpicpgx.org/v1/guideline` and `recommendation_view` | None in the client | Client pages with `Range` of 1000 rows and retries HTTP 429 and 5xx. A published rate limit was not on the license file | Guideline `version` integer when the API sends it. Database tag not returned by the client | Not stored | The client refetches. It does not use a delta feed. No delta feed is claimed |
| CPIC files | HTTPS XLSX and PDF | Document 31 records HTTP 200 and 404 on `files.cpicpgx.org` `current` paths. Document 74 records PDF URLs | None recorded | Not measured | `Last-Modified: 26 October 2026` on the workbooks that sent it. `current` is not a version | Not retained | Replacing `current` without saving the old file destroys history |
| ClinPGx | HTTPS JSON | Code path `/v1/data/gene` and `/v1/data/clinicalAnnotation`. Landing page `https://api.clinpgx.org/` fetched | None on the landing page | Landing page: 2 requests per second, then HTTP 429. The page asks for email before non-trivial use | Not a release number. The page says the API is not yet the final stable API | Not seen | Not seen |
| ClinVar summary | HTTPS gzip of a tab-delimited file | Code URL and the README fetched this pass | None | The client retries 408, 429, and 5xx and supports Range resume | README: generated weekly, archived monthly. Archive file names include the month | Gzip CRC is checked by the downloader. An external md5 was not seen in the client | No. The weekly file is a full snapshot. The code does not download the monthly archive name |
| ClinVar and dbSNP and OMIM fallback | NCBI E-utilities | Code and document 31. NCBI policy page states the scripting rules | Optional `NCBI_API_KEY`. Email and tool name are requested by the policy | Policy: no more than 3 requests per second. The gene client waits 0.4 s, which exceeds that | The response is current as of the call. It is not a pinned build unless the build is inside the payload | Not stored | Not a snapshot |
| OMIM official API | HTTPS JSON | Code: `https://api.omim.org/api/entry/search` and `/entry` | `OMIM_API_KEY` | Code waits 0.5 s. The agreement text that might set a limit was not fully retrieved | Not pinned | Not stored | The search extract of the agreement says a downloaded database must be refreshed at least weekly. That clause is `partial` |
| gnomAD | Policies page names public download. The file URL was not opened | `https://gnomad.broadinstitute.org/policies` | Not stated on that page | Not stated | The page’s citation example gives v4.1 and the date 19 April 2024 | Not seen | Not seen. Do not invent a bucket URL |
| MANE | The description page names FTP in GFF3, GTF, FASTA, and GenBank, plus Entrez and NCBI Datasets | MANE page fetched. FTP README not opened | Not stated | Not stated | The page discusses v1.5 and says later releases are expected about yearly | Not seen | Full release files, not a delta |
| HGNC | About page only | No download URL was on the fetched about page | Not stated | Not stated | Not stated | Not seen | Not seen |
| MONDO | PURL and GitHub named on the OBO Foundry record | `http://purl.obolibrary.org/obo/mondo.owl` and `https://github.com/monarch-initiative/mondo` | None stated | Not stated | A Git release exists in principle. The tag was not read | Not seen | Release files |
| HPO | README names two PURLs | `http://purl.obolibrary.org/obo/hp.obo` and `hp.owl` | None stated | Not stated | Not read | Not seen | The PURL is “current” unless a release tag is pinned. Pinning a floating PURL is not reproducible |
| Orphadata | FAQ describes XML files twice a year and says an API exists if the user makes contact | No base URL printed | Contact, for the API | Not stated | “Data version (date)” in the requested citation | Not seen | Full XML, June and December |
| FDA table | Public HTML, previously copied to markdown | No API claimed | None | Not applicable | Copy date 23 November 2026 | Not in this pass | Manual snapshot |
| EMA | Legal notice only | No product-information feed was used | Not applicable | Not applicable | Not applicable | Not applicable | Not applicable |

## ClinVar file layout, from the fetched README

| Item | README statement |
|---|---|
| `variant_summary.txt` | Weekly. Latest copy in `tab_delimited`. Monthly copy in the archive |
| XML weekly files | Not archived through the month. They accumulate until the next monthly release |
| Schema | `clinvar_public.xsd`, version in the file name. Release notes describe schema differences |
| Corrections after release | ClinVar may change a file after release to remove personal information that was submitted by mistake |
| Coordinates | Right-shifted, one row per assembly |

A post-release privacy edit means two files with the same month name might differ if a corrected file replaced an archive. The checksum of the bytes actually stored is the reproducibility key. The month name is not sufficient by itself.

## Pagination and filters already in code

CPIC uses an HTTP `Range` header, 1000 records at a time. That is PostgREST pagination. It is not a cursor. A row inserted in the middle of a long read can shift pages. The client does not record a transaction snapshot. A reproducible CPIC ingest needs a database release tag or a dumped file, not only a live paged read.

ClinPGx clinical annotations are truncated in code at 80 rows. That truncation is internal. It is not the API’s completeness.

ClinVar E-utilities search is capped by `retmax`. The FTP path is the one that can be complete, and even that path is then filtered to two significance strings and one gene panel.

## Deprecation and instability that a publisher stated

| Source | Statement retrieved |
|---|---|
| ClinPGx API | Parameters and responses may change until a final release is announced on the blog |
| CPIC license file | Database and API contents may lag the guideline page and may be unavailable |
| HPO PURL | The README gives the PURL as the current download. A PURL that always points at “latest” cannot reproduce an old report |
| ClinVar | Schema versions change. The README keeps a history of XSD versions |

## Access that failed or stayed closed

| Attempt | Result | What is not claimed |
|---|---|---|
| `https://www.pharmvar.org/terms-and-conditions` | Empty body | A working terms endpoint |
| `https://www.pharmvar.org/documentation` | Empty body | API documentation |
| PharmVar `api-service/genes`, prior session | HTTP 401 | A public unauthenticated API |
| `https://cpicpgx.org/license/` | Empty body | Confirmation that the live page matches Git tag v1.53.1 |
| `https://www.clinpgx.org/page/dataUsagePolicy` | Empty body | A complete license. A search extract exists and is marked partial in document 151 |
| `https://www.omim.org/help/agreement` | HTTP 403 | A complete, successfully fetched agreement |
| `https://www.ebi.ac.uk/ipd/imgt/hla/about/termsofuse/` | HTTP 404 | HLA terms |
| Ensembl disclaimer | Timeout | Ensembl legal terms |
| UniProt license | Fallback page, not the license | UniProt terms |
| HGMD index | HTTP 403 | Any HGMD download path |
| DECIPHER data-sharing URL | A search-help page | A data-access protocol |
| gnomAD, MANE, ClinGen, and GenCC data files | Not requested | File sizes, checksum URLs, and authentication |

## Compression and size

ClinVar `variant_summary.txt.gz` is gzip. The code treats the gzip CRC as the integrity check. The uncompressed size and the current compressed size were not recorded this pass, because the file was not downloaded. No other source’s size is stated. Unknown size is not zero.

## What a later client is allowed to assume

Only the rows above. A new source starts as `not_opened` until its official documentation is fetched and, for a file source, one real file is checksummed. A landing page that loads in a browser and returns an empty body to a fetcher is a script shell. It is not evidence of an API.
