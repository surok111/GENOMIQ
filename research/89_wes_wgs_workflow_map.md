# 89. WES/WGS clinical interpretation workflow map

Accessed 23 November 2026. This is a research specification for a future GenomIQ module that would help a geneticist review constitutional single-nucleotide variants, small indels, and, only when the assay claims them, copy-number and structural variants from a VCF. It is not an implemented workflow, not a diagnostic protocol, and not a change to the pharmacogenomic knowledge base.

Document 26 already separates disease interpretation from pharmacogenetic rules. Inheritance and HPO are not required to apply a CPIC recommendation. They are required before any statement about a recessive diagnosis. This document does not make that product decision. It specifies the workflow that would be required if that decision were made later. Document 62 already requires assay scope, genome build, and a refusal when a negative result is not backed by a validated interval. Those rules apply here. A file labeled WES or WGS does not satisfy them.

Nothing in this pass reads a patient file, calls a variant, or assigns a clinical classification.

## What the geneticist needs from the system

The system is a structured review aid. The geneticist remains responsible for the interpretation.

The useful output is a list of candidates that can be inspected one dimension at a time, plus an explicit account of what was not assessed. The geneticist needs:

- A variant identity that survives comparison across files: assembly, contig, position, alleles, and a normalized form.
- Proof of which sample, which assay version, and which reference data versions were used.
- The laboratory’s own quality thresholds, not a threshold copied from another assay.
- A statement of which variant classes and genomic regions the assay has validated.
- Frequency, consequence, gene-disease, and external-classification annotations that keep their source and version.
- Phenotype comparison at the level of HPO terms, including terms that do not match.
- An inheritance statement that stops where genotypes, phase, or parental samples stop.
- A draft report that distinguishes a candidate from an interpretation and an interpretation from a diagnosis.
- A place for a named reviewer to accept, reject, reclassify, or defer, with the machine output left unchanged.

The system must not infer a diagnosis, a penetrance, a missing genotype, a phase, or the absence of disease.

## Boundary

In scope for this specification: VCF validation, sample and phenotype metadata, deterministic annotation and filtering, candidate display, and a laboratory-facing draft.

Out of scope: BAM or CRAM processing, alignment, variant calling, autonomous diagnosis, and any language-model interpretation. Long-read methods are mentioned only as assay classes the laboratory might declare. This module does not analyze long-read files.

WES and WGS share the stages below. They do not share detection capability. Document 91 is the capability matrix. Where a stage needs a fact the assay did not claim, the stage records the gap and continues. It does not fill the gap.

## Record lifecycle

Every variant that enters the file stays in the audit trail. Later stages may set a disposition. They may not delete the row.

| Disposition | Meaning |
|---|---|
| `rejected_input` | The file or the record is not usable. No candidate list is produced from it |
| `no_call` | Genotype missing or explicitly uncalled |
| `low_quality` | A stated laboratory rule failed |
| `quality_unassessed` | A quality field required for the laboratory rule is absent. This is not a pass |
| `not_covered` | No evidence the site was interrogated at the assay’s validated depth |
| `not_in_validated_class` | The variant class is outside the assay’s validation |
| `held_for_review` | Retained for display under the active filter configuration |
| `deprioritized` | Retained, with the rule that lowered its display rank |
| `excluded_by_rule` | Hidden from the default candidate list and still present in the audit, with the rule name |
| `human_classification` | Set only by a named reviewer. The software does not write this value |

`excluded_by_rule` is a display decision. It is not a benign classification and not a negative diagnostic result.

## Stage map

The stages run in this order because later annotations are meaningless on a broken record. Phenotype and inheritance do not delete technical failures. Report text is generated only from rows that still carry their dispositions.

1. Input validation.
2. Sample identity and metadata validation.
3. Reference genome and annotation compatibility.
4. Variant normalization and representation.
5. Quality control.
6. Population frequency annotation and filtering.
7. Consequence annotation.
8. Clinical evidence annotation.
9. Phenotype matching.
10. Inheritance assessment.
11. Candidate prioritization.
12. Detailed candidate review.
13. Report generation.
14. Human review and sign-off.

Reference data used by stages 6 through 10 are pinned before stage 6. A pin is a source name, version or release date, assembly, and the file or query that was used. An unpinned source is not applied.

## 1. Input validation

Purpose. Decide whether the file is a VCF this module is allowed to read, and whether each record is structurally usable.

Required inputs. The VCF text or an equivalent tabular decode. A parser allow-list of VCF versions. Document 90 defines the field contract.

Expected outputs. A file-level acceptance or `rejected_input`. A record-level acceptance, `rejected_input`, or `no_call`. Counts of records read, rejected, and accepted. The declared `##fileformat`.

Common failures. Missing `##fileformat`. A version outside the allow-list. A header that does not match the body. A record with the wrong number of columns. An ALT allele that is not a sequence, a symbolic allele, or a breakend as defined by the declared VCF version. A sample column without a header name. A truncated file. Mixed assemblies in one file.

Automatable. Syntax, version allow-list, column counts, header consistency, and duplicate sample names.

Human review. Whether a rejected file should be regenerated by the laboratory. The software does not repair a VCF.

Must not be inferred. A missing FILTER is not PASS. A missing FORMAT field is not a default depth or genotype. A sites-only VCF is not a genotype. A gVCF reference block is not a variant. An undeclared INFO key may be retained as text and must not be interpreted.

## 2. Sample identity and metadata validation

Purpose. Bind the VCF columns to laboratory samples and to the clinical question, without inventing relationships or phenotypes.

Required inputs. One opaque `sample_id` per genotyped column, an `assay_id` and `assay_version`, a `test_scope`, and the genome build, as in document 62. Optional: pedigree, affected status, karyotypic sex as reported by the laboratory, specimen type, and an order flag for secondary findings. Optional HPO terms are validated in stage 9; their presence is only checked here.

Expected outputs. A sample manifest. A stated proband, if and only if the order names one. A family graph taken from the pedigree file, or `family_not_supplied`. A list of metadata fields that are missing.

Common failures. Two columns with the same name. A metadata sample with no column. A column with no metadata. More than one person and no statement of who is the proband. Pedigree parents who are not columns. Affected status left as the PED unknown code and then treated as unaffected. A tumor specimen submitted to a germline workflow.

Automatable. Identifier crosswalk, uniqueness, and completeness of mandatory metadata. Refusal of the run when `sample_id`, `assay_id`, `assay_version`, or genome build is missing.

Human review. Any discrepancy between reported sex and sex-chromosome ploidy. The discrepancy is a QC flag. It is not a new sex assignment. Relationship errors in the pedigree.

Must not be inferred. Clinical sex, gender, ancestry, consanguinity, or affected status from the VCF. A first column is not the proband. A parent who was not sequenced is not reference. A parent sequenced and reported as unaffected is not a proof of non-penetrance.

## 3. Reference genome and annotation compatibility

Purpose. Prevent a coordinate from one assembly being read with annotations from another.

Required inputs. Declared build, `GRCh37` or `GRCh38`, matching document 62. The VCF `##contig` or `##reference` lines when present. The assembly of every annotation source that will be applied. A written liftover policy if, and only if, the laboratory asks for liftover.

Expected outputs. `compatible` or `rejected_input`. The contig naming map actually used (`1` versus `chr1`). A list of contigs that will not be interpreted, including unplaced and alternate contigs unless the assay has a rule for them.

Common failures. Build omitted. GRCh37 coordinates annotated with gnomAD v4, which is a GRCh38 callset. GRCh38 coordinates annotated with gnomAD v2.1.1. `hg19` treated as identical to GRCh37. `chrM` and `MT` mixed. Variants on ALT contigs compared with primary-chromosome frequencies.

Automatable. Equality of declared builds across the VCF and each pinned source. Rejection when they differ. Application of an approved contig alias table.

Human review. Whether a failed liftover should be repeated. This module does not run liftover unless a later, separate specification authorizes a named tool and version. Unlifted records stay `ambiguous_variant`.

Must not be inferred. The build, from chromosome length or from a nearby rs identifier. An rs identifier can be mapped to more than one assembly and more than one allele. A successful-looking coordinate match is not a liftover.

## 4. Variant normalization and representation

Purpose. Give each allele one comparison key without destroying the laboratory’s original record.

Required inputs. CHROM, POS, REF, ALT, and the reference sequence version used for normalization. A stated normalization procedure. The procedure is not chosen in this research pass. A future implementation must name the tool, version, and reference FASTA.

Expected outputs. Original alleles. A normalized, left-aligned, parsimonious representation for each alternative allele. A decomposition of multiallelic records into per-allele rows that still point at the original record. A flag when the record is a symbolic structural allele, a breakend, a multi-nucleotide substitution, or a gVCF non-reference allele.

Common failures. The same indel written at two positions. A multiallelic record annotated as if only the first ALT existed. A multi-nucleotide variant split into SNVs that are then interpreted separately. A structural variant represented only by a breakpoint with no end and no type. Comparison of unnormalized alleles to a database of normalized alleles, producing a false “not in database.”

Automatable. Decomposition and normalization when the reference FASTA and the tool are pinned. Identity checks that REF matches the reference FASTA at POS.

Human review. Records whose REF does not match the FASTA. Multi-nucleotide and complex alleles. Any structural record the assay did not validate.

Must not be inferred. That normalization changed the biology. That a split allele is phased with the other alleles from the same record. That a symbolic allele has a precise breakpoint. That two nearby SNVs are one haplotype event.

## 5. Quality control

Purpose. Apply the laboratory’s validated rules and to mark everything else as unassessed.

Required inputs. The assay’s minimum depth, minimum genotype quality, allele-fraction behavior, and fail labels for FILTER. Per-sample GT, and, when the rule uses them, DP, AD or equivalent counts, GQ or likelihoods, and caller-specific artifact annotations. A coverage summary or a gVCF if any negative statement will be made.

Expected outputs. Per-call disposition: `low_quality`, `quality_unassessed`, `no_call`, or accepted for further annotation. A sample-level QC summary. Regions relevant to the phenotype that fall below the assay’s own threshold, once phenotype and gene lists exist. Those regions are `not_covered`, not reference.

Common failures. FILTER `.` stored as PASS. Site DP used as if it were sample DP. A heterozygous call with no allelic depths. Strand-bias tags from one caller read with another caller’s thresholds. A variants-only VCF used to claim that a gene was negative.

Automatable. Comparison with numeric thresholds the laboratory supplied. Counting of unassessed fields.

Human review. Borderline depth, allelic imbalance, and any call in a region document 91 marks as difficult. The software flags imbalance. It does not decide that the call is an artifact or that it is mosaic.

Must not be inferred. A universal depth. Document 62 forbids copying one. The ACMG 2021 sequencing standard says laboratories set their own minimum and gives examples only. Those examples are not thresholds for this module. Mosaicism, contamination, or sample swap, beyond raising a flag the laboratory’s rule already defines.

## 6. Population frequency filtering

Purpose. Attach frequencies and, only when the disease parameters exist, compare them with a predeclared maximum credible frequency.

Required inputs. A pinned frequency resource on the same assembly. At least allele count, allele number, homozygous or hemizygous count, and a population label when the resource provides one. For a frequency conclusion, the disease prevalence, genetic heterogeneity, allelic heterogeneity, penetrance, and inheritance mode used in the comparison, each with a source. The rule set in document 92.

Expected outputs. Frequencies with the population they came from. `frequency_not_compared` when any parameter is missing. A deprioritization or exclusion reason when a predeclared rule fires. The rule text, not a bare “common.”

Common failures. One global cutoff. gnomAD allele frequency treated as a benign classification. Absence from gnomAD treated as pathogenic. A frequency from an ancestry group that does not represent the patient, with no statement of that limit. Homozygous count ignored for a recessive question. A variant excluded from the audit instead of deprioritized.

Automatable. Lookup, match on normalized alleles, and arithmetic comparison when every parameter is present and pinned.

Human review. The choice of prevalence, penetrance, and heterogeneity. Any variant that is frequent in one labeled group and absent in others. Any use of frequency in a poorly represented group.

Must not be inferred. The patient’s genetic ancestry from a VCF. A population label is not a clinical ancestry assignment. Penetrance. That “rare” means pathogenic or that “common” means benign. Document 92 states this restriction in full.

## 7. Consequence annotation

Purpose. Show what a pinned transcript set says the allele does, including disagreement across transcripts.

Required inputs. A pinned transcript source, with versions. A pinned annotator and cache. The normalized allele. The laboratory’s transcript policy: MANE Select when the laboratory has adopted it, a named RefSeq or Ensembl transcript, or `transcript_not_selected`.

Expected outputs. For each selected transcript: HGVS coding and protein strings if the annotator produced them, a consequence term, the exon or intron, and the predicted protein change. A list of other transcripts with a different consequence. An empty HGVS field when the annotator did not produce one.

Common failures. A gene-level “loss of function” taken from a non-coding transcript or from a transcript the laboratory does not use. A synonymous variant dropped before splice annotation. HGVS written without a transcript version. Consequences compared across RefSeq and Ensembl without saying so.

Automatable. Running the pinned annotator and storing every consequence it returns for the selected transcripts.

Human review. Picking a transcript when the policy does not select one. Interpreting a predicted splice effect. Deciding that a premature stop is loss of function for that gene. The ACMG/AMP framework, including the later PVS1 recommendations, is a human classification method. This stage does not apply it.

Must not be inferred. A clinical classification from a consequence term. Protein damage. That the canonical splice consequence is pathogenic. That a prediction score is a functional study.

## 8. Clinical evidence annotation

Purpose. Attach external assertions and their conflicts, without adopting them as the laboratory’s class.

Required inputs. Pinned releases of the resources the laboratory enables. At minimum, the specification expects slots for ClinVar, a gene-disease validity source, and a place for primary literature identifiers. Empty slots stay empty. Document 92 defines how they may affect display. Document 98 says which resources are references rather than required dependencies.

Expected outputs. Zero or more assertions, each with condition, classification, review status, submitter or curator type, and date. A conflict flag when assertions disagree. The gene-disease validity label for the condition under review, or `not_curated`. A field for the laboratory classification that remains unset.

Common failures. A majority vote across ClinVar submitters. A pathogenic assertion for a different condition transferred to the patient’s phenotype. An expert-panel assertion treated as if this laboratory had reviewed the evidence. A drug-response assertion mixed into a Mendelian classification. PP5 or BP6 applied from the star rating. ClinGen’s sequence-variant group recommended that those two criteria be discontinued because the assertion is not the evidence.

Automatable. Retrieval, version pinning, and conflict detection by inequality of classifications within the same condition and allele.

Human review. Every assertion that will appear in a report. Resolution of conflicts. Any upgrade or downgrade relative to an external class.

Must not be inferred. The laboratory’s ACMG/AMP class. That a high review status removes the need to read the evidence. That an unreviewed submission is either right or wrong. That absence from ClinVar is evidence of benignity or of novelty in a clinical sense. Novelty still requires the frequency source and the match method.

## 9. Phenotype matching

Purpose. Compare the patient’s stated HPO terms with the phenotypes curated for a gene-disease pair.

Required inputs. HPO identifiers marked as observed, excluded, or not assessed. Age or an onset term when the laboratory collected one. A pinned HPO release and a pinned disease-to-phenotype annotation. Document 93.

Expected outputs. Per candidate and per disease: matched terms, patient terms with no match, disease terms not observed, excluded terms that conflict with the disease annotation, and terms that were not assessed. A phenotype disposition. If no HPO terms were supplied, `phenotype_not_supplied` for every row, and no phenotype rank.

Common failures. Free text stored as if it were an HPO term. A parent term expanded into every child. An adult-onset feature counted as a mismatch in an infant. An excluded term ignored. A missing term treated as an excluded term. A similarity number shown without the terms that produced it.

Automatable. Ontology lookup, exact and ancestor comparison, and information-content calculation on a pinned corpus. The arithmetic must be reproducible from the stored terms.

Human review. Whether the HPO list fairly represents the patient. Mapping of free text. Judgement when a highly specific term conflicts and when it does not.

Must not be inferred. Unstated phenotypes. A typical presentation for the disease. That a good match confirms the variant. That a poor match refutes it. Incomplete penetrance and age-dependent expression are the reasons.

## 10. Inheritance assessment

Purpose. Test whether the observed genotypes are compatible with a stated inheritance pattern, and to stop when the test cannot be performed.

Required inputs. Zygosity for the proband. Sex chromosomes interpreted only with the laboratory’s reported karyotype and the ploidy rules in document 94. Optional parental genotypes, phase, and an affected-status field that uses unknown rather than a default. The inheritance label curated for the gene-disease pair, or `inheritance_not_stated`.

Expected outputs. One of: compatible, incompatible with the samples tested, or `inheritance_not_assessable`, plus the missing fact that blocked assessment. A separate flag for apparent de novo, apparent compound heterozygosity, and homozygous observation. Each flag names the evidence and the missing confirmation.

Common failures. Two heterozygous variants in a recessive gene reported as a compound heterozygote without phase. A variant absent from an untested parent called de novo. A heterozygous variant called incompatible with recessive inheritance when a second allele may be unseen. A mitochondrial diploid genotype treated as heteroplasmy.

Automatable. Mendelian consistency checks on the samples that are present. Comparison of zygosity with the curated pattern. Emission of `inheritance_not_assessable` when parents or phase are absent.

Human review. Every apparent de novo and every possible compound-heterozygous pair. Parentage. Reduced penetrance when an unaffected parent carries the allele. Mosaicism.

Must not be inferred. De novo status, cis or trans, parent of origin, or a diagnosis. Document 94 lists the conclusions that are unavailable without parents or phase.

## 11. Candidate prioritization

Purpose. Order the review list so that a geneticist can see why each row is high or low, without collapsing the reasons into one score.

Required inputs. The dispositions and annotations from stages 5 through 10. A written sort configuration. Document 95.

Expected outputs. An ordered list. For each row, the value of every dimension. The configuration identifier. A count of rows excluded from the default view and the rules responsible.

Common failures. A weighted score that cannot be unpacked. A phenotype rank that hides a quality failure. A rare variant promoted because it is rare. A single “top hit.” An empty list presented as a negative genome.

Automatable. A documented lexicographic sort on named fields. Stable ordering so that equal rows do not swap between runs.

Human review. Any change to the sort configuration. The decision to report a row. The decision that no row is worth reporting.

Must not be inferred. A probability of diagnosis. A clinical priority that overrides a documented dimension. That the first row is the cause.

## 12. Detailed candidate review

Purpose. Put one candidate, and the evidence against it, on one inspectable surface.

Required inputs. The stored dimensions, the original and normalized alleles, the transcript consequences, the pinned sources, and the missing-data list. Document 96.

Expected outputs. A review record the geneticist can accept as a candidate, set aside, or hold. No classification is written unless the reviewer writes it.

Common failures. A page that shows only supporting facts. A frequency rendered with more precision than the allele count supports. An HGVS string that does not name the transcript version. A hidden default that filled missing phase with trans.

Automatable. Assembly of the stored fields and highlighting of missing fields.

Human review. This stage is the human review of the evidence. The software does not complete it.

Must not be inferred. Any fact that is not in the stored record. Uncertainty is shown by naming the missing input. It is not shown by a confidence percentage the inputs cannot support.

## 13. Report generation

Purpose. Render a laboratory draft that a reviewer can sign, edit, or reject.

Required inputs. The review records the reviewer marked for inclusion, the QC summary, the assay limitations, the filter audit, and the statements for candidates that were not included. Document 97. An empty inclusion set is a valid input.

Expected outputs. A draft with the sections in document 97. A result class of candidate, evidence-supported interpretation, established diagnosis, incidental finding, or inconclusive. Established diagnosis appears only when a reviewer has recorded that decision. The draft itself never selects that class.

Common failures. “No pathogenic variant detected” when the candidate list is empty. Omission of genes that were not covered. A filter count that cannot be traced to a rule. Secondary findings included after the order opted out, or omitted without saying the order opted out.

Automatable. Filling the draft from stored fields and refusing to fill a field that was not stored.

Human review. Every sentence that will leave the laboratory. Wording of limitations. The result class.

Must not be inferred. A negative diagnosis. A recommendation for a specific next test beyond the classes of missing evidence already stored, such as “parental samples were not available” or “this variant class was not validated.” The specification does not authorize a treatment recommendation.

## 14. Human review and sign-off

Purpose. Separate the machine draft from the laboratory’s result.

Required inputs. The draft, the identity of the reviewer, the date, and the reviewer’s disposition for each included and excluded candidate the policy requires them to see.

Expected outputs. A signed record or an explicit unsigned state. Amendments are new records. They do not overwrite the draft.

Common failures. A stored classification with no reviewer. A later software rerun that replaces the signed text. A signer who cannot see the version pins.

Automatable. Check that required dispositions are present before the record can be marked signed. Preservation of the unsigned draft.

Human review. The entire content. Sign-off is a laboratory act, not a software state that can be defaulted.

Must not be inferred. That a completed run is a signed report. That agreement with ClinVar is a signature.

## Failure handling across stages

If stage 1 or stage 3 rejects the file, stages 4 through 13 do not produce a candidate list. The report, if one is emitted at all, says the file was rejected and why.

If stage 2 finds the proband unspecified in a multi-person file, inheritance and phenotype stages do not run. Sample-level QC may still run.

If a single record fails normalization or the reference base check, that record is `ambiguous_variant` and the rest of the file may continue.

A stage that lacks an optional input records the specific not-assessed state. It does not repeat earlier stages with a guess.

## What remains a laboratory responsibility

Analytical validation, the choice of frequency parameters, transcript policy, secondary-findings policy, confirmatory testing policy, and the clinical interpretation. ACMG’s 2021 constitutional NGS standard assigns those choices to the laboratory. This workflow gives the laboratory a place to record them. It does not supply them.

## Sources read for this map

- Rehder and colleagues, Genetics in Medicine, 29 April 2021, “Next-generation sequencing for constitutional variants in the clinical laboratory, 2021 revision.” The article states that exome coverage is not uniform, that genome sequencing examines over 90 percent of the genome rather than the whole of it, and that laboratories set coverage thresholds for their own assays.
- VCFv4.5, 25 February 2026, samtools hts-specs printing e821e4f. Used for the file-level objects this workflow accepts. Field rules are in document 90.
- Documents 26 and 62 of this research series. Used for the boundary between pharmacogenetic interpretation and disease interpretation, and for the refusal rules on build, scope, and negative results.

## What this document does not authorize

No parser, no filter, no report template, and no knowledge-base edit. A future implementation is a separate decision, and only after the disease-interpretation scope in document 26 is explicitly accepted.
