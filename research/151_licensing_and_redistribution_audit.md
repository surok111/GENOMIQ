# 151. Licensing and redistribution audit

Accessed 23 November 2026. Technical access is not legal permission. A public page can still forbid redistribution, commercial use, or derivative databases. Where the license text was not retrieved, the source is unresolved. Unresolved means do not ship it. This note is not legal advice. Several rows require counsel before a customer deployment.

## What “use” means in this audit

| Act | Question |
|---|---|
| Download | May GenomIQ retrieve a copy for internal research? |
| Store | May that copy be kept as an immutable snapshot? |
| Transform | May fields be parsed and normalized? |
| Extract | May a subset of fields be kept? |
| Redistribute | May the transformed subset be given to a customer? |
| Report | May a report quote or derive a sentence from it? |
| History | May old snapshots be kept after a new release? |

A “request” in a CC0 instrument is not the same as a license condition. The audit still records the request, because dropping attribution would violate the publisher’s stated practice even when the dedication does not make it a legal duty. Counsel decides which requests are operational requirements.

## Licenses retrieved in full enough to quote

| Source | Instrument retrieved | What it permits, in its own terms | What it restricts or requests | Redistribution judgement |
|---|---|---|---|---|
| CPIC curated content | `cpic-data` `LICENSE.md` at tag v1.53.1, fetched | CC0 1.0. “Freely available for use by anyone.” “Free of restriction” | Requests attribution, citation, version and date for API content, and a warning that content changes. Logo and acronym need NIH permission for advertising. Points at a live license page that returned an empty body. Disclaimer: tables omit nuance and are not a treatment order | Internal storage, transformation, and historical snapshots fit the CC0 text. Customer inclusion of CPIC tables is the CC0 grant, plus the attribution request. Do not use the logo. Re-read the live license page before publication because the fetched file delegates the API agreement to a page this pass could not read |
| ClinGen curated content named on the terms page | `https://www.clinicalgenome.org/docs/terms-of-use/`, fetched | CC0 for gene-disease validity, dosage sensitivity, and clinical actionability | Requests attribution and the access date. Logo needs approval. VCI has a separate agreement that was not opened | The named curation types may be stored and redistributed under that CC0 sentence. VCI content is not included |
| GenCC | `https://thegencc.org/terms`, fetched | CC0 | Requests attribution to GenCC and to contributing sources | The GenCC classification file, once downloaded, fits that sentence. Contributor websites, especially OMIM, are not included |
| gnomAD primary exome and genome data | Policies page, fetched | CC0. Any purpose. No legal duty to attribute. No publication embargo | Do not re-identify participants. Do not put gnomAD in the product name or use the logo. SpliceAI annotations inside the release are CC BY-NC 4.0, academic and non-commercial, Illumina. Attribution is requested | Frequency tables may be stored and shipped if SpliceAI and any other restricted annotation are removed or separately licensed. A customer report may cite a frequency with the release name |
| HGNC | About page, fetched | “No restrictions are imposed on access to, or use of, the data” | No warranty | Storage and redistribution of a pinned HGNC file are consistent with that sentence. The download index was not opened, so confirm the file that is actually shipped carries the same statement |
| FDA website | Website policies, fetched | Unless otherwise noted, text and graphics are public domain and may be republished without permission | Copiers should date the copy and link back, because pages change. Not a substitute for a clinician | The associations table may be snapshotted and quoted. A stale copy is an operational hazard the policy itself describes |
| EMA website | Legal notice, fetched | Reproduction and distribution, commercial and non-commercial, with EMA acknowledged on each copy. Citations allowed | Third-party content is excluded. Logo needs written permission. An online file may not be the adopted text | The legal notice may be quoted. Product-information pharmacogenetic sections are not cleared, because the copyright holder of each document was not checked |
| Orphadata Science | FAQ, fetched | CC BY 4.0, including commercial use, with credit and an indication of changes | Do not imply endorsement. Do not add further restrictions. Logos need approval. A service that uses the data in an AI tool offered to others needs a statement that Orphanet is not responsible for the outputs. Products need a contract | Science XML may be stored, transformed, and shipped with attribution and a change note. Products may not. Historical snapshots are compatible with CC BY if the version is cited |
| MONDO | OBO Foundry record, fetched | CC BY 4.0 | Attribution. The OWL file header was not yet checked | Ship only after the file header matches. Keep the version |

NCBI molecular databases, from the fetched policy: NCBI places no restrictions on use or distribution of those databases and does not accept restricted submissions. Submitters may still claim rights, and NCBI cannot transfer a right it does not hold. This covers a ClinVar archive, dbSNP, Gene, and RefSeq as NCBI molecular data. It does not make every sentence in a ClinVar submission a work of the U.S. government. Counsel should confirm whether wholesale redistribution of submission text needs anything beyond the NCBI policy. Quoting an aggregate classification, a review status, an identifier, and a condition name in a laboratory report is the use this specification allows. It is not a claim that every long submitter comment is cleared.

The same NCBI page lists OMIM and Bookshelf as copyrighted material with their own terms.

## Partial or failed, and therefore not cleared

| Source | What happened | Decision |
|---|---|---|
| ClinPGx / PharmGKB data-usage policy | Direct fetch returned an empty body. A search extract of the official URL contains CC BY-SA 4.0 and a separate clause that the data are for research and are not to be offered for sale as a commercial item. The API landing page says all API data are subject to that policy | Legal review required. Do not ship ClinPGx annotations or pathway figures to customers. Internal research download is how the existing client already behaves, and even that should pause for counsel if the deployment is commercial. Share-alike, if it is the real license, would bind derivative databases that are distributed |
| CPIC live license page | Empty body. The GitHub file incorporates it by reference | Do not treat the GitHub file as the last word on the API until the live page is read |
| PharmVar terms | Empty body. Prior API call was HTTP 401. An HL7 page’s CC BY-SA sentence is not the PharmVar license | No download and no redistribution |
| OMIM agreement | HTTP 403 on fetch. A search extract includes a non-transferable, non-sublicensable license, a ban on selling or transferring the data, a paid license for commercial download, and a weekly-refresh clause for databases | Legal review required. Do not populate or ship `omim_entries`. Do not treat the NCBI fallback as a way around the agreement. The code path exists and is not a grant |
| IPD-IMGT/HLA | Terms URL returned HTTP 404. Sequences were retrieved in an earlier task | Do not redistribute those sequences. A name already published in a paper can be cited as a name |
| Ensembl | Disclaimer timed out | No Ensembl bulk redistribution |
| UniProt | License page did not load | No UniProt dump |
| HPO | README links to a license page that was not opened | No HPO redistribution until that page is read |
| GeneReviews and Bookshelf | NCBI says they have their own notice. The notice was not opened | Quote only a chapter that was already retrieved, inside research. Do not ship the series |
| PanelApp | Only a search extract of a December 2019 PDF, which restricts commercial and diagnostic use | No ingestion |
| DECIPHER | Agreement not found at the URL that was fetched | No patient data |
| HGMD | HTTP 403 | No ingestion |
| SNOMED CT | Not opened | No embedding |
| DPWG / KNMP | Not opened | No monograph text |
| EMA product information | Website notice excludes third-party content | No bulk SmPC |
| gnomAD SpliceAI track | Restricted on the gnomAD policy page | Strip it from any shipped release |
| GIAB, LOVD, BRAVO, dbVar, UCSC tracks, VEP, ANNOVAR | Terms not opened | No redistribution |

## Report text

A report may contain:

- A CPIC recommendation that a reviewer published, with the guideline version, the URL, and the access or snapshot date.
- An FDA table sentence from the dated local snapshot, identified as the FDA table and not as a label.
- A ClinVar aggregate or SCV assertion identified as ClinVar, with the release, the condition, and the review status. The report must not present it as GenomIQ’s class.
- A gnomAD count identified by release, without SpliceAI.
- A ClinGen or GenCC validity label identified by release.
- An HGNC symbol and ID from a pinned file.
- A Mondo or Orphanet identifier under the CC BY terms, with attribution available in the report or its annex.

A report may not contain OMIM prose, HGMD citations copied from an unlicensed download, PharmVar haplotypes, ClinPGx levels, DPWG sentences, SNOMED terms, or HPO labels from a file whose license is unread. An HPO identifier that a laboratory typed may appear as the laboratory’s input. That is not a redistribution of the HPO release.

## Historical snapshots

CC0 and public-domain dedications allow retention of old copies. CC BY requires the version and the attribution to travel with the copy. The OMIM extract’s weekly-refresh clause, if it survives in the full agreement, conflicts with an ordinary “keep every snapshot” design. That conflict is one reason OMIM is not ingested. ClinVar’s own README says a file may be corrected after release to remove personal data. An immutable snapshot that contains such data is a privacy problem, not only a license problem. The raw store needs a documented process for a publisher’s privacy takedown that preserves the checksum history without continuing to distribute the removed identifiers.

## Flags for counsel

1. ClinPGx: CC BY-SA versus the no-sale sentence in the unread full page, and whether a customer deployment is “offered for sale.”
2. OMIM: whether any current use, including the NCBI fallback and the SQLite schema, is permitted without a Johns Hopkins license.
3. ClinVar submission text beyond identifiers and aggregate classifications.
4. CPIC live API page, once it can be read, against the GitHub CC0 file.
5. PharmVar, before any key is requested.
6. EMA and DPWG documents, before any label or monograph is stored.
7. HPO, before phenotype ranking is shipped.
8. PanelApp, before any diagnostic use. The 2019 extract says diagnostic use needs a separate agreement.

No source is cleared for redistribution merely because a client can download it today.
