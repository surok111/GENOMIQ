# 143. Variant database source audit

Accessed 23 November 2026. Population-frequency resources and clinical-assertion resources are different objects. A frequency does not classify a variant. An assertion does not state how common the allele is. This document does not accept any imported assertion as a GenomIQ classification.

## ClinVar

Publisher: National Center for Biotechnology Information, U.S. National Library of Medicine.

Official locations read this pass:

- FTP README, `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/README.txt`, header “Last updated January 13, 2026.”
- The ingest URL in code: `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz`.
- NCBI data policy, `https://www.ncbi.nlm.nih.gov/home/about/policies/`, fetched this pass. See document 151.

The README describes `variant_summary.txt` as a weekly tab-delimited report, archived monthly on the first Thursday of the month. Most variants have one row for GRCh37 and another for GRCh38. The current parser keeps one row per `VariationID` and prefers GRCh38. That is an internal choice, not a property of the file.

What the summary actually provides, from the README text:

| Content | In `variant_summary` | Limit written in the README |
|---|---|---|
| Variant identity | `AlleleID`, `VariationID`, `Name`, `Type` | AlleleID and VariationID are different. The October 2016 change restricted the file to AlleleID attributes |
| Coordinates | `Assembly`, `Chromosome`, `ChromosomeAccession`, `Start`, `Stop` | Start and Stop are right-shifted, pter to qter. They are not a left-aligned VCF allele |
| Alleles | `ReferenceAllele`, `AlternateAllele` | Right-shifted. An August 2020 note says an earlier VCF-style representation was reverted |
| Gene | `GeneID`, `GeneSymbol`, `HGNC_ID` | `HGNC_ID` is present for a single gene and is `-` otherwise. The README’s GeneSymbol sentence says a comma-separated list. The parser splits on comma, semicolon, and pipe |
| Aggregate classification | `ClinicalSignificance`, `ReviewStatus`, `ClinSigSimple`, `LastEvaluated` | The significance is an aggregate germline classification. It gives precedence to submissions with assertion criteria. `ClinSigSimple` can therefore disagree with `ClinicalSignificance`. The README gives the example of a no-criteria pathogenic submission plus criteria-bearing benign submissions |
| Conditions | `RCVaccession`, `PhenotypeIDs`, `PhenotypeList` | If one RCV has more than five conditions, the file reports the count instead of the identifiers |
| Submitter count | `NumberSubmitters`, `SubmitterCategories` | A count is not the submitter’s text |
| Other identifiers | `RS# (dbSNP)`, `nsv/esv (dbVar)`, `OtherIDs` | rs is `-1` when missing |
| Origin | `Origin`, `OriginSimple` | Germline and somatic are distinguished only as far as `OriginSimple` |
| Structural variants | `Type`, and the dbVar identifier | The gene-level file text says structural variants that overlap a gene are excluded from one pathogenic count. The summary still has a type field. This ingest does not interpret structural type |
| Individual submissions | Not this file | The README describes SCV as the accession of a submitted interpretation. The XML release is the place those records live. It was not downloaded |

The current parser keeps a row only when the aggregate significance is exactly `Pathogenic` or `Likely pathogenic`. Conflicting, uncertain, benign, likely benign, risk, drug-response, and low-penetrance strings are dropped even when they are the clinically important fact. That filter makes the staging table a watch list for the local gene panel. It is not a ClinVar mirror and it cannot feed the conflict display in document 92.

Recommended role: clinical assertion source, quotation only, after the ingest retains the aggregate string it actually filtered out, the assembly it dropped, and a pointer to SCV-level records when a conflict or a condition list is truncated. Not a laboratory classification. Not a frequency source.

Versioning: weekly file, monthly archive named by month in `tab_delimited/archive/`. The staging table stores `source_retrieved_at` and a row hash. It does not store the archive name. Two downloads in the same week can be different files. The release identity has to be the archived file name or the README’s release note, not the clock.

## dbSNP

Publisher: NCBI.

Document 31 records E-utilities `esummary` calls on 23 November 2026 for a named set of rs identifiers. The summary confirmed that the rs existed and named a gene. It did not return coordinates, the reference allele, or a transcript. The same summary can carry a blended clinical-significance string. Document 31 refused that string as allele function. Document 74 S18 records build 157, released 3 September 2024, only for pages that printed that build.

This pass applied the NCBI molecular-data policy to dbSNP as an NCBI molecular database. The dbSNP FTP directory and the current build number were not re-downloaded.

What dbSNP is for: a stable rs identifier and, when a specific build’s VCF or JSON is pinned, alleles on that build. One rs can name more than one alternate allele. An rs is not an allele definition and not a clinical class.

Recommended role: optional identifier cross-reference. Not a clinical assertion source and not a frequency source. Frequency belongs to a population callset that states its sample.

Access: E-utilities, already in code. NCBI’s scripting guidance, fetched this pass, says no more than 3 requests per second, an email and a tool name, and no large series during Eastern Time weekday hours. The gene-database client uses a 0.4 second interval, which is faster than that guidance. That gap is an operational defect, not a license.

## gnomAD

Publisher: the gnomAD consortium, Broad Institute. Policies page `https://gnomad.broadinstitute.org/policies` was fetched this pass.

The page says the primary exome and genome data are under the Creative Commons Zero public-domain dedication. It also says some annotations are restricted. The example given is SpliceAI, computed by Illumina and provided under CC BY-NC 4.0 for academic and non-commercial use. Users must not try to re-identify participants. The project name and logo are not available for another product’s name. The page’s own citation example for v4.1 is “807,162 individuals, released on 04/19/2024.”

The download files, checksums, and the exact HTTPS or cloud URLs were not opened this pass. Document 92 already records the v4.0 and v4.1 announcements from an earlier task: GRCh38, joint allele numbers, and an exome-versus-genome discordance flag. Those announcement pages were not re-fetched today. The policies page is the licensing evidence. The announcement is not re-cited as a new verification.

What gnomAD provides when a release is pinned: allele count, allele number, filtering allele frequency, ancestry-group counts, homozygous counts, and, in v4, structural and copy-number callsets. It does not provide a clinical classification. The v4.0 announcement, as previously read, said phenotype metadata are incomplete and disease subsets were not offered. Affected people can be present. Absence from a site that was not covered is not absence from the population.

Recommended role: population frequency reference for GRCh38 once a release file and its checksum are pinned. SpliceAI and any other non-CC0 annotation stay out of the redistribution package unless their own license is satisfied. Not a benign catalog.

## LOVD

Leiden Open Variation Database. Instances are gene-specific and are run by different curators. The LOVD site and its license were not opened this pass. Status: `not_opened`.

What a future check has to answer before any use: which instance, who curates it, whether the variant-to-phenotype rows are case reports or classified variants, and whether that instance’s license allows storage and redistribution. A public HTML page is not that permission.

Recommended role until then: none. Do not add LOVD as a silent second ClinVar.

## BRAVO and TOPMed

The BRAVO browser and the TOPMed data-use terms were not opened. Status: `not_opened`.

BRAVO is a frequency browser over TOPMed genomes. Some TOPMed data sit behind dbGaP controls. A public browser count and a redistributable file are not the same object. No endpoint is claimed here.

Recommended role: none until the public-file terms are read. It is a candidate frequency resource for groups that gnomAD represents poorly, not a replacement for gnomAD and not a clinical database.

## dbVar

The ClinVar README names an `nsv/esv` column. The dbVar website, FTP, and license were not opened. Status: `not_opened`, except for the fact that ClinVar points at it.

dbVar is a structural-variant archive. An nsv identifier is not a confirmation that the event matches a short-read caller’s breakpoint. Recommended role, if later verified: identifier crosswalk for structural variants. Not a clinical classification and not proof of an assay’s detection limit.

## HGMD

`https://www.hgmd.cf.ac.uk/ac/index.php` returned HTTP 403 this pass. The public and professional licenses were not read. Status: `failed`.

HGMD is not added. A 403 is not evidence about the contents. Document 151 forbids ingestion until the publisher’s current license is read. The public subset, if it exists, is not assumed to be redistributable.

## How these sources must not be merged

| Question | Source that may answer it | Source that must not answer it |
|---|---|---|
| Has a submitter asserted a condition relationship? | ClinVar SCV, or the aggregate only if it is labeled as an aggregate | gnomAD, dbSNP, BRAVO |
| How many alleles were seen in a named callset? | A pinned gnomAD release, or another pinned frequency release | ClinVar’s “not in ClinVar,” dbSNP’s clinical string |
| What is a stable public identifier? | rs, VariationID, AlleleID, nsv, each stored as its own identifier | Treating any one of them as the allele |
| Is the allele left-aligned on GRCh38? | A normalizer and a pinned FASTA | ClinVar’s right-shifted Start and ReferenceAllele |

The current ClinVar hash fields are `VariationID`, `RS#`, `GeneSymbol`, `GeneID`, `ClinicalSignificance`, `ReviewStatus`, `LastEvaluated`, `Origin`, `Name`, `Type`, `Assembly`, `Start`, `Stop`, `ReferenceAllele`, and `AlternateAllele`. They omit `ClinSigSimple`, `PhenotypeList`, `RCVaccession`, and `HGNC_ID`. A change that only alters the condition list does not change the hash. That is a real gap in the existing ingest, read from `src/clinvar_ingest/hashing.py`.

## Recommendation

Use ClinVar as the clinical-assertion archive and gnomAD as the frequency archive. Keep dbSNP as an identifier. Leave LOVD, BRAVO, dbVar, and HGMD unused until their own terms and files are read. Do not let the existing pathogenic-only filter become the definition of ClinVar.
