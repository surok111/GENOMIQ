# 144. Pharmacogenomic source audit

Accessed 23 November 2026. A guideline, an allele-definition database, a literature annotation, and a regulatory table are four different evidence types. They are not interchangeable. Dose text is copied only from the document that contains the dose. Allele function is copied only from the table that states the function.

## CPIC

Publisher: Clinical Pharmacogenetics Implementation Consortium. The database is reached through ClinPGx infrastructure. The GitHub organization is `cpicpgx`.

License file fetched this pass: `https://raw.githubusercontent.com/cpicpgx/cpic-data/v1.53.1/LICENSE.md`.

That file says curated CPIC content is under CC0 1.0. It requests attribution, citation of the paper, a warning that content changes, and a citation of the form CPIC, URL, date accessed, plus the version number for API or database downloads. It says the CPIC logo and acronym may not be used in advertising without NIH permission. It says the database and API are bound by `https://cpicpgx.org/license/`. A direct fetch of that live page returned an empty body. The GitHub text is verified. The live page is not. The tag `v1.53.1` was the URL that returned the license. This pass did not prove that the local JSON files are that tag.

The disclaimer in the same file says guideline nuance may be absent from a downloaded table, that the API may lag the guideline page, and that the clinician and the patient decide treatment. A stored recommendation is not a GenomIQ order.

What CPIC provides, from the code and from documents 20, 31, and 74:

| Content | Where it was actually seen | Interchangeable with |
|---|---|---|
| Guideline identity, name, URL, PMID, year, version integer | API client and `research/sources/cpic_guidelines.json` | Nothing else |
| Drug-specific recommendation text and strength | `recommendation_view`, when the row was in the extract. Warfarin id 100425 returned none. Tricyclic rows were page-limited | Not the FDA table. Not a DPWG percent |
| Phenotype bins | PDFs that document 74 marks as retrieved, for example the 2022 clopidogrel Table 1 | Not a local combined “RM/UM” label |
| Allele definition on a named workbook | HTTP 200 workbooks on 26 October 2026 for the genes listed in document 31 | Not PharmVar, until PharmVar itself is read |
| Allele clinical function and activity value | The function workbooks opened in that same work | Not a blog note about an unpublished value |
| Co-gene conditions | Only the guideline tables that were read, as catalogued in documents 67 through 71 | Not an inference from a shared pathway |

Download and API, verified from code and from the license file:

- REST: `https://api.cpicpgx.org/v1/guideline` and `recommendation_view`. PostgREST `Range` pagination. No API key in the client.
- Files previously retrieved: `https://files.cpicpgx.org/data/report/current/allele_definition/{GENE}_allele_definition_table.xlsx` and the matching `allele_function_reference` path. The `current` path is a moving target. A snapshot has to copy the bytes and record Last-Modified or, better, a dated archive URL if one exists. This pass did not open a dated archive index.
- Update cadence is per guideline. The license text says users must check that they have the current content. There is no single “CPIC version” that covers every gene unless the database tag is pinned.

Recommended role: pharmacogenomic guideline, and, for workbooks that are snapshotted, allele-definition and allele-function reference. Not a regulatory mandate. Not an automatic dose in a report until a reviewer publishes the rule.

## PharmVar

Publisher: Pharmacogene Variation Consortium.

This pass fetched `https://www.pharmvar.org/terms-and-conditions` and `https://www.pharmvar.org/documentation`. Both returned an empty body, consistent with the script shell document 31 already found on the gene pages. The API call recorded there, `https://www.pharmvar.org/api-service/genes`, returned HTTP 401, “API Key is invalid or missing.” No key was used then and none was used now.

An HL7 terminology page quotes a CC BY-SA 4.0 claim and points at the PharmVar terms URL. That HL7 page is not the PharmVar terms. It is not used here as the license.

A PharmVar standards PDF was identified at `https://www.pharmvar.org/documents/PharmVar%20Standards.pdf` by search. It describes PharmVar IDs as immutable for a haplotype definition: a changed variant set retires the ID and issues a new one, while a star-name change can keep the ID. The PDF was not re-fetched as a full file in this pass. The ID rule is therefore `partial`, from the search extract of that PDF, and it is not a license.

What PharmVar is for, once the terms and a keyed snapshot exist: haplotype definitions, star names, core alleles, structural alleles, and evidence level for the definition. It is the allele-definition authority CPIC workbooks are not a substitute for. Document 31 already says that.

What was not established: whether a key is free, whether redistribution of a transformed allele table is allowed, whether commercial deployment is allowed, the rate limit, or the current release number.

Recommended role: none until the terms page returns a readable license and an API snapshot is stored. Do not treat the 401 as “PharmVar has no alleles.”

## ClinPGx, formerly PharmGKB

Publisher: the ClinPGx project. The API landing page `https://api.clinpgx.org/` was fetched. It describes a REST JSON interface for annotations and reference objects. It says the endpoints are not yet a final stable API and that parameters may change. It applies the ClinPGx data-usage policy and asks for notice before non-trivial use. It sets a limit of 2 requests per second and says faster traffic receives HTTP 429.

The data-usage policy URL `https://www.clinpgx.org/page/dataUsagePolicy` returned an empty body on direct fetch. A search extract of that same URL contained both a Creative Commons Attribution-ShareAlike 4.0 grant for ClinPGx/PharmGKB data and a terms clause that the data are for research and are not to be offered for sale as a commercial item. The extract also distinguishes CPIC guidelines from other dosing guidelines on the site. Because the direct fetch was empty, document 151 marks this license unresolved and requires legal review before customer redistribution.

The code already calls `/v1/data/gene` and `/v1/data/clinicalAnnotation`. Clinical annotations have a level of evidence that belongs to ClinPGx. That level is not a CPIC strength and not an ACMG class.

ClinPGx also hosts text about CPIC and about DPWG. Hosting is not authorship. A CPIC row must cite CPIC. A DPWG row must cite DPWG and the monograph that was opened. A ClinPGx clinical annotation must cite ClinPGx and its level.

Recommended role: optional literature-annotation index, after the license is resolved. Not a guideline. Not an allele definition.

## DPWG

Publisher: the Dutch Pharmacogenetics Working Group, through KNMP. The primary monograph site was not opened this pass and was not opened in the earlier ledger.

What the project has used:

- A 2019 European Journal of Human Genetics table, document 74 S11.
- A Medical Genetics Summary that reprints a table titled DPWG 2025, document 74 S23, marked secondary.
- Failed attempt to filter the ClinPGx API with `source=dpwg` (HTTP 400). That failure says the property was wrong. It does not say DPWG is absent.

DPWG and CPIC disagree in places this project has already recorded, including warfarin dose method. Document 154 keeps both. Neither is selected because it is newer.

Update mechanism, download, and redistribution rights of the KNMP text: `not_opened`.

Recommended role: none as a primary source until the monograph and its terms are read. Secondary quotations stay labeled secondary.

## FDA

The Table of Pharmacogenetic Associations was saved on 23 November 2026 as `research/sources/fda_pgx_associations_2026-11-23.md`. This pass fetched the FDA website policy, `https://www.fda.gov/about-fda/about-website/website-policies`. Unless otherwise noted, FDA website text and graphics are not copyrighted and are in the public domain. The policy asks copiers to record the copy date and to link back, because the agency updates pages and stale copies can cause harm. Credit is requested and not required.

The table is a regulatory association list. It is not a drug label. Document 74 states that label PDFs named in the local files were not opened. A table row that says “see the labeling” does not contain the label’s dose.

Recommended role: regulatory source for the associations table, snapshotted with the copy date. Labels remain unread and are not inferred from the table.

## EMA

The legal notice `https://www.ema.europa.eu/en/about-us/legal-notice` was fetched. Website content is © EMA 1995–2026. The notice allows reproduction and distribution, including commercial, if EMA is acknowledged on each copy, and citations with acknowledgement. It excludes third-party content. It says an online document is not guaranteed to be the officially adopted text. The logo requires written permission.

Product information was not opened gene by gene. The legal notice does not say that every summary of product characteristics is EMA-authored. A marketing-authorisation holder’s document can be third-party content. Bulk redistribution of SmPC pharmacogenetic sections is not cleared by the website notice alone.

Recommended role: no ingestion now. A later, label-specific check can add a regulatory source distinct from CPIC and from FDA.

## Other professional sources

PharmCAT is named in the ClinPGx policy extract as having its own license section. The PharmCAT license was not opened. PharmCAT is an implementation of guidelines, not a guideline.

CPIC/DPWG consensus papers, such as the CYP2D6 terminology paper cited as PMC6951851, are journal articles. They were used in earlier tasks. Their publisher licenses were not re-read. A consensus terminology paper is not the allele-function workbook and not the current guideline PDF.

National bodies other than FDA and EMA were not surveyed.

## Separation the knowledge base has to keep

| Evidence type | May supply | Must not supply |
|---|---|---|
| PharmVar allele definition | Haplotype variants, star name, PharmVar ID, structural allele | A dose |
| CPIC function workbook | Activity value and clinical function status for that CPIC version | A PharmVar ID that was not in the file |
| CPIC guideline | Phenotype translation and the recommendation at its stated strength | A claim that the same sentence is FDA labeling |
| ClinPGx annotation | A literature-based level, with the PMID | A CPIC strength |
| DPWG monograph | A DPWG recommendation, only after the monograph is read | A “European” dose that merges CPIC and DPWG |
| FDA table | The association and the table’s action language | The unread label’s dose |
| EMA product information | Nothing, until the document and its copyright holder are identified | A substitute for the FDA table |

## Programmatic access, stated only where seen

| Source | Seen | Not seen |
|---|---|---|
| CPIC API | Code path, no key, Range paging | A machine-readable release manifest in the local client |
| CPIC workbooks | Prior HTTP 200 and 404 | A retained checksum |
| PharmVar API | Prior HTTP 401 | A successful payload. Rate limit. License |
| ClinPGx API | Landing page and the code’s two endpoints | The Swagger file. Stability beyond the landing page’s warning |
| DPWG | Nothing programmatic | Everything |
| FDA table | A local markdown copy. The website policy | A structured JSON feed. None is claimed |
| EMA | The legal notice | A product-information API used for pharmacogenetic sections |
