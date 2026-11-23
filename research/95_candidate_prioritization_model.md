# 95. Candidate prioritization model

Accessed 23 November 2026. This document defines a transparent, multi-dimensional review order for constitutional variants. It does not define a diagnostic score. A row’s place in the list is an order of inspection. It is not a probability and not a classification.

Every dimension remains visible on the row. No dimension may be replaced by a weighted sum. If two rows differ, a reviewer must be able to see which dimension differs. If they do not differ, they tie.

The model consumes documents 90 through 94. It does not relax them.

## Dimensions

Each dimension has a small set of named states. States are ordered only where the order is stated. A missing input is a state, not a zero.

### 1. Technical reliability

States, from more usable to less usable: `meets_laboratory_rules`, `quality_unassessed`, `low_quality`, `no_call`.

`low_quality` and `no_call` do not enter the default inspection list. They remain in the audit. `quality_unassessed` enters the list with a badge. A technically failed call is never rescued by phenotype or by ClinVar.

### 2. Assay capability

States: `class_validated`, `class_validated_difficult_region`, `class_not_validated`, `coverage_not_shown`.

`class_not_validated` leaves the default list and appears in the limitations. `class_validated_difficult_region` stays, badged, and does not outrank a clean call on phenotype alone. `coverage_not_shown` applies to negative gene statements, not to an observed variant. An observed variant with failing coverage is a technical-reliability problem.

### 3. Gene-disease validity

States from the pinned curation: Definitive, Strong, Moderate, Limited, Conflicting, Disputed, Refuted, No reported evidence, `not_curated`.

The order of inspection for the stated indication places Definitive and Strong before Moderate, then Limited, then not curated. Conflicting, disputed, and refuted are not placed at the bottom as if unseen. They are placed in a visible conflict group. A gene without a curation for the indication can still be inspected. It is not described as unrelated to disease in general.

Validity is specific to the disease. A gene that is definitive for a different disease does not inherit that label for the indication.

### 4. Variant-disease evidence

States: `external_assertion_for_this_condition`, `external_assertion_for_another_condition`, `no_external_assertion`, `evidence_conflict`, `primary_evidence_pointer`.

An external assertion is a quotation with its review status and date. It is not the laboratory class. `evidence_conflict` outranks a clean assertion in the inspection order so that conflict is seen first, not smoothed. A pointer to a paper is not ranked above an assertion and is not ranked as no evidence. It has its own state.

The laboratory classification is not a dimension the software fills. When a reviewer has set it, it is displayed as reviewer data and the sort does not silently change.

### 5. Molecular consequence

States are the groups in document 92: predicted loss of function, missense or inframe, canonical splice, splice region, synonymous, UTR or noncoding, deep intronic, regulatory or intergenic, discordant, unassessed.

This dimension sorts only inside a laboratory configuration that has chosen to inspect truncating and splice alleles first. The default configuration does that, and it records the choice as a preference of molecular bluntness, not as evidence. A missense allele with a condition-matched external assertion is not buried under anonymous truncating alleles. The assertion dimension is inspected before consequence for that reason. See the sort order below.

Mechanism gates the preference. If the pinned gene-disease record does not say that loss of function is a mechanism, predicted loss of function does not receive the bluntness preference. The state remains visible.

### 6. Population frequency

States: `frequency_not_compared`, `frequency_compatible_with_model`, `above_credible_maximum`, `frequency_unavailable`, `resource_discordant`.

`above_credible_maximum` leaves the default list only when the model in document 92 was complete and the configuration allows exclusion. Otherwise it is a badge. `frequency_compatible_with_model` is not a boost toward pathogenic. `frequency_unavailable` and `frequency_not_compared` are neutral badges. They do not look like rarity and they do not look like benignity.

The numeric frequency, the count, the homozygous count, and the ancestry group are displayed. They are not further compressed.

### 7. Inheritance compatibility

States: `compatible`, `recessive_incomplete`, `incompatible_with_stated_mode`, `inheritance_not_assessable`, `inheritance_not_stated`.

`incompatible_with_stated_mode` stays visible because the incompatibility may be an artifact, a second inheritance mode, or mosaicism. It does not drop the row. `inheritance_not_assessable` is the expected single-sample state for de novo and phase questions and is not a penalty.

### 8. Zygosity and phase

States: heterozygous, homozygous, hemizygous, two alternate alleles, `phase_unknown`, `phase_method_unknown`, `trans_supported`, `cis_supported`, `no_call`.

Phase does not create a higher rank by itself. `trans_supported` changes a recessive pair from `recessive_incomplete` to a paired candidate. The two alleles are shown as one pair and also as two rows, so neither allele is hidden inside the pair.

### 9. Phenotype compatibility

States from document 93: specific overlap, general overlap only, unmatched, conflict, possible conflict, `phenotype_not_supplied`, `phenotype_not_compared`, `disease_phenotype_not_curated`.

Specific overlap raises inspection order. Conflict badges the row and does not remove it. `phenotype_not_supplied` leaves phenotype out of the sort. It does not imitate a mismatch and it does not imitate a match.

### 10. External clinical classification

This is the same information as dimension 4, rendered for the reviewer: significance, review status, condition, date, release. It is listed again because a review screen will have a classification column. The column is a quotation. There is no local five-class value beside it until a person writes one.

### 11. Conflicting evidence

A derived badge, not a new fact. It is present if any of the following is true: ClinVar conflict, gene-validity conflict, consequence discordant across selected transcripts, exome-versus-genome frequency discordant, inheritance incompatible with the stated mode, or a specific phenotype conflict. The badge lists which of those fired. It has no numeric size.

### 12. Missing data

A list, possibly empty: missing depth, missing phase method, missing parents, missing HPO, missing frequency parameters, missing transcript policy, missing coverage for a negative claim. The length of the list is not a score. The list is displayed. A row with missing data that affects the conclusion is badged `incomplete`.

## Default inspection order

The default order is lexicographic. The first field is the primary key. Later fields break ties. The configuration stores this list. A laboratory may reorder it. The result stores the configuration identifier.

1. Technical reliability: rules met before unassessed. Failed and no-call are off the default list.
2. Conflict badge: conflict before no conflict, so disagreements are not buried.
3. Variant-disease evidence for the condition under review: a condition-matched external assertion before no assertion. Conflict is already first because of key 2.
4. Gene-disease validity for that condition: Definitive and Strong, then Moderate, then Limited, then not curated. Refuted for this condition does not use the Definitive slot.
5. Phenotype: specific overlap, then general overlap, then phenotype not supplied, then phenotype compared and unmatched. Conflicts remain in place because key 2 already surfaced them.
6. Inheritance: compatible and trans-supported before recessive-incomplete, before not assessable. Incompatible remains on the list because of the conflict badge.
7. Consequence preference: predicted loss of function and canonical splice before missense, only when the mechanism allows it. Otherwise this key is skipped and the skip is recorded.
8. Frequency: no boost for rare. The only frequency key is a demotion of `above_credible_maximum` when that state was computed. Uncompared frequencies tie.
9. Stable identifier: contig, position, normalized allele, gene. This exists so ties do not change between runs.

What the order deliberately does not do. It does not add points. It does not multiply phenotype by evidence. It does not let a high phenotype key move a `low_quality` row back onto the list. It does not assign 1st place a meaning other than “look here first under this configuration.”

## Required handling of the hard cases

### High phenotype similarity and weak variant evidence

The row stays on the list. Phenotype shows the matched terms. Variant evidence shows `no_external_assertion` or Limited gene validity, whichever is true. Consequence and frequency show their own states. The review text says the phenotype overlap is not independent evidence that the variant is causal. The row must not be deleted for lack of a ClinVar record, and it must not be labeled likely diagnostic.

### Strong variant evidence and poor phenotype match

The row stays on the list. The external assertion and its review status are shown. The unmatched and conflicting terms are shown. Possible reasons that are printed as limitations, not as excuses selected by the software: the phenotype list may be incomplete, the disease may be age-dependent, expressivity may vary, penetrance may be incomplete, or the assertion may concern a different condition. If the condition is different, dimension 4 is `external_assertion_for_another_condition` and the row is not described as strong evidence for the indication.

If the order includes secondary findings and the gene-disease pair is on the laboratory’s adopted list, the row can also appear in the incidental section. It is then an incidental candidate, still without a laboratory class.

### Rare variants of uncertain significance

Rarity does not change dimension 4. A rare allele with no assertion remains `no_external_assertion`. Frequency may be `frequency_compatible_with_model` or `frequency_not_compared`. The row can appear because of consequence and gene validity. The display calls it a rare allele without an established clinical assertion. It does not call it a VUS on the laboratory’s behalf. VUS is a classification a person applies.

### Conflicting ClinVar classifications

`evidence_conflict` is set. Both significances, both review statuses, and the conditions are shown. The row is inspected early because of the conflict key. The module does not choose the majority, the maximum severity, or the newest date. A newer date is displayed. Recency is not a rule.

### Several plausible candidates

All rows that meet the default gates are listed. There is no top-hit field. Pairs that are possible compound heterozygotes are grouped and their members also remain independently visible. The report says more than one candidate remains and that the list is not ranked by probability.

### No plausible candidate

The inspection list can be empty. The result state is `inconclusive`. The audit counts say how many rows were low quality, not in class, deprioritized for a complete frequency model, or left in the expanded view. The phenotype section lists genes relevant to the phenotype that were not covered or not validated. The empty list is not a negative genome and not evidence that no genetic cause exists.

### Incomplete assay coverage

Coverage gaps for genes linked to the stated phenotype are a section of the result, not a variant row. They use `not_covered` and `not_in_validated_class`. They do not generate a synthetic reference genotype. If every variant row is weak and the coverage section is non-empty, the result remains inconclusive and the gaps are printed above any sentence that might be read as a negative.

## What the model refuses

- A single number called a priority, a pathogenicity, a diagnostic score, or a probability.
- A hidden weight that breaks ties.
- Filling a missing dimension with the average of the others.
- Promoting a row because it is the only row left.
- Demoting a row because a more famous gene is also on the list.
- Using the patient’s identity, photographs, or uncoded clinical prose.
- An automated ACMG/AMP point total.

An external tool’s score may be stored under that tool’s name, as document 93 allows for phenotype tools. It is not a dimension in the default order. Adding it to the order is a configuration change and still does not replace the named dimensions.

## Worked patterns, not cases

These patterns exist so a later test can check behavior without using a person.

| Pattern | Expected placement |
|---|---|
| PASS heterozygous, definitive gene, specific HPO overlap, no ClinVar, frequency not compared, parents absent | On the default list. Evidence state is no assertion. Inheritance for de novo is not assessable. Phenotype terms are visible |
| PASS heterozygous, definitive gene, ClinVar pathogenic for this condition with a stated review status, HPO conflict on a specific excluded term | On the default list, conflict badge, both the assertion and the excluded term visible |
| FILTER fail, ClinVar pathogenic | Audit only, under low quality. Not rescued |
| Two heterozygous alleles, recessive gene, no phase | One pair, `phase_unknown`, `recessive_incomplete`. Not labeled compound heterozygous |
| Allele frequency above a complete credible-maximum model | Demoted or excluded only under that configuration, with the parameters printed. Not labeled benign |
| No HPO, otherwise interesting truncating allele in a definitive loss-of-function gene | On the list, `phenotype_not_supplied`, no imputed phenotype |
| Genome VCF, no CNV caller in scope, phenotype associated with a deletion syndrome | No deletion candidate is created. The CNV class is listed as not validated |

## Outputs

For the run: configuration identifier, pins for every resource, count of rows in each disposition, and the ordered default list.

For each row: the state of all twelve dimensions, the sort keys that fired, and the keys that were skipped because an input was missing.

A person may pin, hide, or annotate a row. Those actions are reviewer events. They do not rewrite the automatic order. The report can show the reviewer’s subset and must be able to show that it differs from the automatic list.

## Sources

This model is a local specification. It uses the constraints in documents 91 through 94 and the ACMG, ClinVar, ClinGen, gnomAD, and Whiffin limits cited there. No published ranker was adopted as the order.
