# 97. Clinical report requirements

Accessed 23 November 2026. This document specifies a laboratory-facing draft for constitutional WES or WGS review. The draft is an input to human sign-off. It is not a report until a named reviewer signs it. It is not a patient letter. It does not recommend a drug dose and it does not replace a clinical genetics consultation.

The draft is allowed to be inconclusive. An empty candidate list is a valid draft. It is not proof that no genetic cause exists, and the draft must say that in the result section rather than in a footnote only.

No patient report was generated for this research.

## Result classes

The draft carries exactly one result class. The class is chosen by the reviewer. The software may refuse to emit a class the stored evidence does not support. It may not choose the class.

| Class | When it is allowed | When it is forbidden |
|---|---|---|
| Candidate finding | One or more variants are included for review and no laboratory classification has been signed | Forbidden as a synonym of pathogenic |
| Evidence-supported interpretation | A reviewer has written an interpretation that cites the stored evidence and stops short of a diagnosis | Forbidden if the text adds evidence that is not in the review record |
| Established diagnosis | A reviewer has explicitly recorded that decision under the laboratory’s policy | Forbidden as a software default. Forbidden from phenotype rank, ClinVar, or zygosity alone |
| Incidental finding | The order included a secondary-findings analysis, the gene-disease pair is on the adopted list, and the reviewer includes it | Forbidden when the order opted out. Forbidden as a surprise section. The ACMG SF list is a policy a laboratory may adopt, not a list this module applies on its own |
| Inconclusive | The reviewer does not include a candidate, or includes only unresolved findings | Forbidden to be worded as a negative diagnostic test of the genome |

A draft may also name unresolved findings inside an inconclusive or candidate report. Unresolved is a section, not a quieter form of benign.

## Required sections

Sections are omitted only when the section header remains and the body says why the section does not apply. They are not dropped.

### 1. Input and QC summary

- Opaque sample token, assay identifier, assay version, test date if supplied.
- Genome build and reference FASTA identifier.
- VCF fileformat version, caller and version if known, normalizer and version.
- Sample manifest. Proband designation or the statement that no proband was designated.
- Family samples actually analyzed, or `family_not_supplied`.
- Counts: records read, rejected, no-call, low quality, quality unassessed, accepted for annotation.
- The laboratory thresholds used. If a threshold was not supplied, the sentence says the corresponding check did not run.
- Sex-chromosome QC flag, if one was raised, without a reassigned karyotype.

### 2. Assay limitations

- Method family: exome or genome, as declared. The declaration is not a capability claim.
- Variant classes in scope and classes not in scope, using document 91’s words.
- Capture or analysis intervals: supplied, or not supplied. If not supplied, gene-level negatives are stated to be unavailable.
- Difficult regions and named homologous loci that were not specifically validated, including CYP2D6, HLA, and the other ACMG 2021 examples when those genes are relevant to the indication or to a secondary-findings list the order included.
- Mitochondrial analysis: performed with a stated limit of detection, or not performed.
- Repeat expansions, methylation, and structural variants: assessed only if in scope.
- Confirmation policy: stated, or `not_stated`. Unstated is not a waiver.
- A sentence that short-read sequencing does not examine every disease mechanism and that a genome does not remove homologous-region limits.

### 3. Filtering statistics

For the named configuration:

- each rule that changed a disposition
- the count of rows that received that disposition
- the statement that an excluded or deprioritized row remains in the audit
- frequency model parameters, or the statement that frequency was not used as a screen
- consequence groups included in the default view
- a statement that counts are not counts of benign or pathogenic variants

### 4. Phenotype

- HPO terms with observed, excluded, or not assessed.
- Ontology and annotation versions, or `phenotype_not_supplied`.
- Age or onset if supplied.
- The indication as stated by the order.
- Matches and mismatches summarized from document 93, with the full term table available to the reviewer. The signed report includes at least the matched terms, the specific conflicts, and the fact that unobserved disease terms were not treated as absent findings.
- A sentence that phenotype overlap is not confirmation.

### 5. Candidate variants

For each included candidate, the identity block from document 96: build, coordinates, transcript version, HGVS if complete, zygosity, phase phrase, quality, consequence, frequency with counts, external assertions with conflicts, gene-disease validity, and the reviewer’s classification if one exists.

If the reviewer includes none, the section says no candidate was selected for the draft. It does not say no candidates were found unless the automatic list was also empty, and even then it uses the inconclusive wording below.

### 6. Prioritization rationale

- configuration identifier
- for each included row, the dimension states that placed it on the list
- for rows the reviewer removed, the reviewer’s reason
- a statement that the order is not a probability

This section is allowed to be short. It is not allowed to be a single score.

### 7. Inheritance assessment

For each included variant or pair: the sentence document 94 permits, the samples used, and the conclusions that were not assessable. If no family was supplied, one sentence says parental genotypes were not available and de novo and trans were not assessed. That sentence is required even when the candidate list is empty, if the indication includes a disorder for which de novo or recessive phase would have mattered. The report does not guess which disorders those are beyond the gene-disease records that were actually retrieved for the phenotype. If phenotype was not supplied, the inheritance section says family analysis was not requested or was not possible, whichever is true.

### 8. Evidence summary

For each included candidate: supporting observations, contrary observations, and “no contrary item is stored” when that is the case. External classes are quoted. The laboratory class is attributed to the reviewer or marked not set.

Conflicts are repeated here even if they also appear in the candidate section. A summary that mentions only the pathogenic assertion is a failed draft.

### 9. Unresolved findings

- quality-unassessed calls the reviewer should know about, summarized rather than dumped, with a pointer to the full audit
- possible compound-heterozygous pairs with unknown phase
- apparent de novo observations that are not confirmed
- genes linked to the phenotype that are not curated
- external conflicts the reviewer did not resolve

Unresolved is not a second candidate list. It is a limit on what the draft knows.

### 10. Additional testing considerations

This section lists missing evidence classes. It does not order a test.

Permitted sentences are of the form “parental samples were not part of this analysis,” “phase was not established,” “copy-number variants were not in the validated scope,” “this locus is homologous and no locus-specific assay was declared,” or “coverage for the following phenotype-related intervals was not shown.”

Forbidden sentences are a named laboratory order, a clinical recommendation, or a claim that a particular follow-up would find the cause. The reviewer’s own recommendation, if the laboratory’s policy allows one, is placed in the reviewer comment and attributed to the reviewer.

### 11. Technical limitations of the analysis software

- reference releases and the date they were pinned
- annotator and normalizer versions
- filters that did not run because an input was missing
- pre-annotated VCF fields that were not trusted
- the statement that the software does not assign ACMG/AMP criterion codes and does not sign the report

### 12. Human review and approval

- reviewer identity and role
- date
- result class
- a statement that the reviewer examined the contrary evidence and the assay limits
- signature state: unsigned draft or signed
- version of the draft that was signed

An unsigned draft is watermarked as unsigned in the text, not only in a file attribute. A later rerun does not change a signed version. It creates a new draft.

## Wording that is required for an empty or negative-looking result

When no candidate is included, the result class is inconclusive unless the reviewer has recorded a different decision the evidence allows. The required meaning, in the laboratory’s own words, is all of the following:

- No variant was advanced as a diagnostic finding in this draft.
- This is not a demonstration that the phenotype has no genetic cause.
- Variant classes and regions that were not validated were not excluded.
- A variant that was filtered out of the default view may still be in the audit.
- Parental, phase, and phenotype limitations apply as documented in their sections.

The phrase “no pathogenic variant detected” is not used unless the reviewer has actually classified the relevant variants and the assay scope covers the mechanisms of the diseases under consideration. Even then, the sentence is the reviewer’s and is accompanied by the limitations. The software does not offer that phrase as a template for an empty list.

“Normal genome” and “negative exome” are not result classes.

## How the classes look in the draft

| Situation | Class | Headline meaning |
|---|---|---|
| Reviewer includes a rare missense allele with no laboratory class | Candidate finding | Included for clinical review. Not a diagnosis |
| Reviewer writes that the allele is pathogenic for the condition and that the phenotype is compatible, and stops there | Evidence-supported interpretation | An interpretation. The diagnosis of the patient is still a clinical act |
| Reviewer records an established molecular diagnosis under laboratory policy | Established diagnosis | Attributed to the reviewer and the policy. The software stores it |
| Reviewer includes an ACMG SF gene the order opted in, unrelated to the indication | Incidental finding | Separate from the indication. Not a diagnosis of the presenting disease |
| Empty inclusion set | Inconclusive | No candidate advanced. Cause not excluded |
| Strong ClinVar assertion and a specific phenotype conflict, reviewer unwilling to resolve | Inconclusive, with the conflict in unresolved findings | The conflict is the result, not a silent omission |

A report can contain an indication section and an incidental section. They are not added into one diagnosis. An incidental finding does not explain the presenting phenotype unless the reviewer explicitly says so.

## Secondary findings

The order has three states: opted in to a named list and version, opted out, or not stated.

| Order state | Draft behavior |
|---|---|
| Opted in | The incidental section uses that list and version. A match is a candidate for the reviewer, not an automatic incidental report. Genes on the list that were not adequately covered are listed as not assessed |
| Opted out | The incidental section says the order opted out. Matches are not promoted |
| Not stated | The incidental section says the order did not state a policy. The module does not apply ACMG SF v3.3 or any other list by default |

ACMG SF v3.3 was identified as the June 2025 policy statement that adds genes to v3.2. The gene table was not copied into this specification on purpose. A future module that implements secondary findings must pin the version the laboratory adopted and must treat it as a minimum reporting policy, not as a disease filter for the indication and not as a screen of the population. The 2025 statement itself says secondary findings are not a replacement for indication-based testing and not a form of population screening.

## Traceability

Every sentence that states a fact about the sample cites a stored field. Every sentence that states a fact about a database cites a pin. Free text is confined to the reviewer comment. The draft generator fills templates. It does not write a new scientific claim.

The audit annex, which may be a separate file, contains the dispositions that the signed report only summarizes. The signed report names the annex by version. A report that cannot be traced to the annex is not complete.

## What the report must not contain

- A probability of diagnosis.
- A language-model narrative.
- A patient name or a medical-record number. The sample token is enough for the laboratory draft. Identifiers for a clinical system are a later privacy decision and are out of scope here.
- A pharmacogenetic dose. Pharmacogenetic reporting remains the separate stack in document 26.
- An automatic “pathogenic” label copied from ClinVar.
- A statement that untested parents are reference, that unphased alleles are in trans, or that an unvalidated variant class was excluded.

## Sources

- Documents 89 through 96 for the fields the draft is allowed to render.
- Rehder and colleagues, 2021, for the expectation that coverage limits and difficult regions are reported and that complete coverage is not expected.
- ACMG SF v3.3 policy statement, Genetics in Medicine, 23 June 2025, PMC12318660, for the boundary between secondary findings and diagnostic testing. The gene list was not reproduced.
- Document 17 of this series is a pharmacogenetic report specification. It is not reused as this draft. The two products must not share wording that turns a genotype into a prescription or a phenotype rank into a diagnosis.

No report template was implemented.
