# 157. Source prioritization

Accessed 23 November 2026. Priority is not importance in the abstract. A clinically central source with an unread license stays out of the build. The two domains are prioritized separately because a CPIC table does not make a genome review valid, and a ClinVar archive does not make a dose.

Tiers:

| Tier | Meaning |
|---|---|
| 1 | Required for a first useful, citable product in that domain, and clear enough to pin |
| 2 | Needed for broader coverage after tier 1 is snapshotted |
| 3 | Specialist material for hard loci or a second evidence type |
| 4 | Research-only, blocked, or deferred |

## Pharmacogenomics

| Tier | Source | Why |
|---|---|---|
| 1 | CPIC guidelines through the API, saved as bodies, plus the PDFs for rules that are actually published | The recommendation and phenotype authority the project already uses. CC0 text was fetched from the GitHub license. The live license page still has to be re-read |
| 1 | CPIC allele-function and allele-definition workbooks, retained with checksums | The only allele definitions this project successfully read. They are not PharmVar, and the role must say so |
| 1 | HGNC release | Stable gene identity for the panel matcher. The about page permits use. The file still has to be downloaded |
| 1 | FDA Table of Pharmacogenetic Associations, dated snapshot | Regulatory layer, public-domain website policy fetched. Not a label |
| 2 | MANE, for the transcripts named in those workbooks | Stops HGVS from floating. Not required to display a CPIC star recommendation that does not use HGVS |
| 2 | NCBI Gene and the RefSeq accessions printed on the workbooks | Identity crosswalk |
| 3 | PharmVar | The right allele authority, including structural alleles, once the terms page is readable and a key is granted |
| 3 | IPD-IMGT/HLA | HLA names. Redistribution of sequences is blocked until terms are found |
| 4 | ClinPGx clinical annotations | Useful index. License unresolved, including a possible no-sale clause |
| 4 | DPWG monographs | Important disagreements with CPIC. Primary text and license not opened |
| 4 | EMA product information | Regulatory, and third-party copyright is not cleared |
| 4 | PharmCAT | An implementation, not a source |
| 4 | `KNOWN_VARIANTS` | Retire rather than extend |

First useful pharmacogenomic product means: a reviewer can see a CPIC recommendation and the allele function it depends on, with versions, and can distinguish it from the FDA table. It does not mean every drug in the local files has a dose.

## WES and WGS review aid

This tier list assumes the product decision in document 26 is eventually to build a review aid, not a diagnostic engine. Document 99 already said that decision is open. The order below is the source order if that decision is made.

| Tier | Source | Why |
|---|---|---|
| 1 | Reference FASTA for GRCh38, and GRCh37 only if a laboratory still submits it | No coordinate is interpretable without it. NCBI molecular-data policy was fetched. The FASTA checksum was not |
| 1 | MANE release | Default transcript. Page fetched. File not yet snapshotted |
| 1 | HGNC release | Gene identity |
| 1 | ClinVar monthly archive, both assemblies, all significance values, snapshot checksum | Assertion source. The current pathogenic-only ingest is not this pin |
| 1 | gnomAD release file without restricted annotations | Frequency. Policy fetched. File not yet opened |
| 1 | ClinGen gene-validity release | Validity layer. Terms are CC0. File not yet opened |
| 2 | ClinVar XML or submission summary, for SCV-level conflicts | The aggregate file hides the disagreement the review aid must show |
| 2 | GenCC release | Second validity submitter. CC0 terms fetched |
| 2 | MONDO release, after the OWL header matches CC BY | Disease identifier |
| 2 | HPO release and the disease-annotation file | Phenotype ranking. Blocked on the unread license page |
| 2 | Orphadata Science gene and disease files | Rare-disease names. CC BY retrieved. Not a validity grade |
| 3 | ClinGen dosage file | Needed when CNV review is in scope |
| 3 | gnomAD SV and CNV files | Frequency of structural events, after those files are identified |
| 3 | dbSNP build VCF | Identifier crosswalk, not a class |
| 3 | GIAB | Validation only, after NIST terms are read. Not knowledge |
| 3 | Laboratory BED files | Assay scope. Supplied by the laboratory, not downloaded from a vendor on assumption |
| 4 | OMIM full text | License fetch failed. Not required if ClinGen, GenCC, and Mondo identifiers exist |
| 4 | HGMD | HTTP 403. Not a public redistributable source on the evidence in hand |
| 4 | PanelApp | Diagnostic use is restricted in the only terms extract found |
| 4 | DECIPHER patient data | Agreement not retrieved |
| 4 | LOVD, BRAVO, dbVar | Not opened |
| 4 | SNOMED | Not opened and not required for an HPO-based review aid |
| 4 | GeneReviews as a bulk text | Bookshelf terms not opened |
| 4 | VEP, SpliceAI, ANNOVAR | Tools. SpliceAI redistribution is restricted. None is tier 1 knowledge |

## Shared tier 1 across both domains

HGNC and a pinned assembly or transcript accession policy serve both. CPIC does not serve the genome review. ClinVar and gnomAD do not serve a dose. The shared infrastructure is the snapshot store, not a shared clinical meaning.

## Effort and update burden

| Source | Implementation effort | Update burden |
|---|---|---|
| CPIC API, once bodies are saved | Low. The client exists | Per guideline and per database tag. A live page can drift |
| CPIC workbooks | Low. URLs are known | The `current` path changes without notice. Snapshot every retrieval |
| ClinVar archive | Medium. The downloader exists and the filter has to stop discarding rows | Weekly generation, monthly archive, occasional privacy replacement |
| gnomAD | Medium. Large files. Strip restricted annotations | Major and minor releases, not daily |
| ClinGen and GenCC | Low once the file URL is verified | Curation releases. The URL was not verified |
| HPO and MONDO | Low after license and header checks | Regular ontology releases. Reports must pin |
| PharmVar | Unknown until the API key terms are known | The partial standards extract says definitions are versioned by retiring IDs |
| OMIM | Do not start | The partial agreement extract would require at least weekly refresh |

## Recommendation

Build the snapshot and license record first. Then pin CPIC and the FDA table for pharmacogenomics, and pin assembly, MANE, HGNC, full ClinVar, gnomAD frequencies, and ClinGen validity for a review aid. Everything in tier 4 waits on a license or a publisher file that this pass did not obtain.
