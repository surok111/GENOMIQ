# 148. Genome, assay, and validation resources

Accessed 23 November 2026. Reference data, validation datasets, and analytical software are three different things. A benchmark does not belong in a clinical knowledge base. A caller does not become a reference because it emits a VCF. Document 91 remains the capability statement. This document only assigns sources.

## Reference assemblies

NCBI reference assemblies GRCh37 and GRCh38 are the builds document 90 accepts. This pass did not download a FASTA, an assembly report, or a checksum. The MANE page confirms that MANE Select matches GRCh38 and that some genes live on patches in v1.5.

A future pin needs the assembly accession, the FASTA checksum, whether alternate contigs and decoys are included, and the mitochondrial sequence. `hg19` and `hg38` are not stored as synonyms until an alias table is written and reviewed. No liftover chain file was opened. Liftover stays out of the pipeline, as document 90 already says.

Recommended role: molecular identity reference. One FASTA per build. Not a clinical database.

## GIAB

The NIST Genome in a Bottle data page was not opened. Status: `not_opened`. No public-domain claim is made from memory.

GIAB, when its terms are read, is a validation dataset: high-confidence regions and benchmark variants for measuring a caller. It is not a list of pathogenic variants and not a population frequency. Recommended role: technical validation resource only, and only after the NIST terms and a specific benchmark version are stored. It must not be loaded into the clinical knowledge base.

## ClinGen technical and curation standards

Two different ClinGen products are easy to mix.

The terms page fetched for document 146 covers curated classifications. It is not a laboratory validation protocol.

ACMG technical standards used in documents 91 and 98, including Rehder and colleagues 2021 and Raca and colleagues 2022, are professional standards. They tell a laboratory how to validate an assay. They are not downloadable interval files. Recommended role: cited technical standard for assay design. Not a BED file and not a gene-disease release.

## Capture kits and BED files

No vendor BED was opened. Status: `not_opened`.

A capture BED is assay content. It is supplied by the laboratory or by the kit vendor under that vendor’s terms. Different kits target different exons. Document 91 already refuses a gene-level negative without the analysis interval. Recommended role: laboratory-supplied assay definition, stored with the kit name and version. Not a public reference GenomIQ should vendor from an unverified URL. A BED found on a company site is not free to redistribute until that file’s terms are read.

## Variant normalization tools

`bcftools norm` and equivalent left-aligners were named in document 98. No tool was run and no license file was opened this pass. htslib’s license is not claimed.

ClinVar’s README says its summary alleles are right-shifted. Any comparison with a left-aligned VCF requires a recorded normalizer, a FASTA, and both coordinate pairs. Recommended role: analytical software, pinned by version, not reference data. The original allele is kept.

## VEP and other annotators

The Ensembl legal page timed out. The VEP license file was not opened. Document 98 already left VEP as an optional annotator pending that license. This pass does not change that.

SpliceAI’s restriction is now also on the gnomAD policies page: CC BY-NC 4.0 for academic and non-commercial use, Illumina-computed scores inside gnomAD. That is a fetched statement about the scores gnomAD distributes. It is not a new reading of the SpliceAI repository, which an earlier task already quoted.

ANNOVAR’s license was not opened.

Recommended role: optional analytical software. Consequence output is an annotation, not a source of clinical truth. Cache version and software version are both part of the identity of an HGVS string.

## Structural-variant and copy-number resources

| Resource | Opened | Role |
|---|---|---|
| ClinVar `Type` and dbVar nsv column | README only | Cross-reference. Not a caller |
| gnomAD SV and CNV callsets | Policies page says primary data are CC0. The SV file and the paper the policies page asks users to cite were not opened | Frequency of a called event, after the file is pinned. Not proof a local assay would have called it |
| ACMG constitutional CNV interpretation standard | Named in document 98. The interpretation page was opened in an earlier task, not today | A human classification method. Not a caller |
| dbVar site | Not opened | None yet |
| A local CNV caller | Not in this repository as a validated pipeline | Analytical software the laboratory would validate. Out of scope for ingestion |

## HLA and pharmacogene tools

IPD-IMGT/HLA release 3.66.0 is the release document 74 recorded for four alleles. The terms URL tried this pass returned HTTP 404. Redistribution of HLA sequences is not cleared.

PharmVar’s CYP2D6 structural documents were opened in earlier research and were not retained. The PharmVar terms page returned an empty body this pass.

Other specialized tools, including PharmCAT, Astrolabe, Aldy, and Cyrius, were not opened. They are callers or diplotype assigners. A diplotype they emit is an assay result, not a knowledge-base fact, unless the allele definition behind it is a pinned PharmVar or CPIC record.

Recommended role: IPD-IMGT/HLA is the nomenclature reference for HLA names already retrieved, with redistribution blocked. Specialized callers are analytical software, not knowledge sources.

## Mitochondrial resources

The revised Cambridge reference sequence is the usual mitochondrial reference. Its GenBank record and license were not opened this pass. Status: `not_opened`.

Document 90 already refuses a diploid genotype as a heteroplasmy result. A mitochondrial reference belongs with the assembly pin. MITOMAP and similar curated mitochondrial-disease resources were not opened. They are not added. gnomAD mitochondrial frequencies, if a release contains them, are a frequency resource only after that file is identified. The policies page did not itemize a mitochondrial product. None is claimed.

## What each assay type may use

| Assay | Reference data that can be pinned now, subject to the license gates | Validation data | Software, not knowledge |
|---|---|---|---|
| Targeted panel | HGNC IDs, the panel’s own BED from the laboratory, CPIC definitions for genes on the panel | The laboratory’s validation, not GIAB until GIAB is read | The laboratory’s caller |
| WES | The same, plus a MANE release and a capture or analysis BED | GIAB only after its terms are read. It does not certify every exon | VEP or another annotator, after its license |
| WGS | Assembly FASTA, MANE, gnomAD frequency once the file is pinned, ClinVar assertions as quotations | GIAB high-confidence regions, after terms | SV and repeat callers, each validated by the laboratory |
| HLA | IPD names already retrieved. Not a bulk sequence redistribution | A laboratory HLA method | Not a whole-genome caller |
| CNV and SV | ClinGen dosage, once that file is pinned. dbVar only as an identifier after its site is read | A benchmark the laboratory names | The CNV caller |
| Mitochondrial | The mitochondrial sequence inside the pinned assembly, after that sequence’s record is read | The laboratory’s heteroplasmy limit | A heteroplasmy caller |

## Recommendation

Separate the shelves. Assembly FASTA, MANE, and HGNC are identity references. GIAB is a validation set and stays out of the knowledge base. Capture BEDs come from the laboratory. Callers and annotators are pinned tools. ClinGen dosage and gnomAD SV frequencies are knowledge or frequency records only after their files, not just their policy pages, are snapshotted. HLA sequences and mitochondrial curated databases stay out until their terms are read.
