# 93. HPO phenotype prioritization

Accessed 23 November 2026. This document specifies how a future module may use Human Phenotype Ontology terms to rank review, and where it must stop. Ranking is not a diagnosis. A phenotype match does not validate a variant. A phenotype mismatch does not exclude one.

No patient phenotype was used. No HPO release was downloaded. An implementation must pin the ontology file and the disease-annotation file. Until those pins exist, no numeric similarity is reproducible, and this specification does not invent one.

## Inputs

| Input | Requirement | If missing or malformed |
|---|---|---|
| HPO identifier, form `HP:` and seven digits | Mandatory for any phenotype ranking | Free text is `phenotype_not_coded`. It is not matched. A person maps it later |
| Observation status: observed, excluded, or not assessed | Mandatory for each coded term | A bare list is treated as observed only if the submitter marks the list as observed. Mixed unmarked lists are `phenotype_status_unspecified` and are not ranked |
| Age at assessment, or an onset term | Optional and strongly recommended | Age-dependent comparison is `not_assessed` |
| The question being asked | The condition or the undiagnosed-phenotype review | A gene match to an unrelated condition is not dropped on the floor. It is labeled as not the stated indication |
| Pinned HPO release | Mandatory before ranking | `phenotype_not_compared` |
| Pinned disease-to-HPO annotations, with the source of each annotation | Mandatory before ranking | `phenotype_not_compared` |
| Gene-disease pair and its validity label | From document 92 | Phenotype overlap does not create a gene-disease relationship |

Not assessed is the correct state for a feature nobody examined. It is different from excluded, and different from a term that is simply absent from the submitted list. Absence from the list is not assessed, unless the laboratory sends a closed form that claims every omitted term was examined and found absent. That claim has to be explicit. The module must not invent it.

## Ontology behavior

HPO is a directed ontology. A child term is more specific than its parent. The true-path convention used in phenotype comparison is: if a patient has a child term, the parent concepts are also true of the patient. That convention has two local consequences.

- The module may treat a patient term as matching a disease annotation when the patient term is the annotation or a descendant of the annotation. The match is labeled `exact` or `patient_more_specific`.
- The module may treat a disease annotation as matched when the disease term is a descendant of a patient term only in a separately labeled way: `patient_more_general`. A parent term such as a broad neurological abnormality matches many diseases and must not be counted as a specific finding.
- The module must not expand a patient parent into every child and then claim those children were observed.
- Obsolete identifiers are resolved only through the pinned ontology’s replacement field. The original identifier is kept. If the ontology offers no replacement, the term is `obsolete_unmapped` and is not dropped silently.

Phenotype specificity is the difference between a match on a broad parent and a match on a narrow child. A ranking that counts matches without showing specificity is not acceptable. For each matched term the display includes the term, its parents up to the point of match, and whether the patient or the disease annotation was more specific.

Information content is one deterministic way to express specificity. For a pinned annotation corpus, the information content of a term is higher when fewer diseases are annotated with that term or its descendants. The usual definitions (Resnik’s information content of the most informative common ancestor, and the Lin and Jiang–Conrath forms that also use the two terms’ own information) are deterministic functions of that corpus. They are not used in this specification as a hidden score. If they are computed, each compared pair shows the term identifiers and the information content of the ancestor that was used. The corpus release is part of the result. A different HPO release is a different number.

This pass did not compute information content for any term and does not recommend a cutoff.

## What is compared

The comparison is between two sets:

- the patient set, partitioned into observed and excluded
- the disease set, taken from the pinned annotations for one gene-disease pair

One gene with two diseases produces two comparisons. Validity and phenotype are not copied from one disease to the other.

| Patient state | Disease annotation | Stored relationship |
|---|---|---|
| Observed, exact or more specific | Present | Supporting overlap. Specificity labeled |
| Observed, only a broad parent | Present as a specific term | Weak overlap, labeled `patient_more_general` |
| Observed | Not in the disease set and not an ancestor or descendant | Unmatched patient term. This is normal. Patients have findings outside one disease |
| Not assessed | Present | Not a mismatch |
| Excluded | Present, and the term is not marked as occasional in the annotation | Conflict, labeled for review |
| Excluded | Present, and the annotation says the feature is occasional, or the disease is age-dependent and the patient is younger than onset | Conflict is downgraded to `possible_conflict` with the reason. It is not deleted |
| Observed | The disease annotation is an explicitly excluding feature | Conflict |

Occasional, frequent, and obligate annotations are different. The HPO annotation format can carry frequency. This pass did not open a current `phenotype.hpoa` file. Until a pinned file is interpreted by a reviewed parser, every disease term is treated as “reported in the disease,” not as “required in every patient.” That choice avoids calling a missing feature a contradiction. It also means the module cannot claim that a disease’s diagnostic criteria were met.

## Age, onset, variability, and penetrance

| Situation | Comparison rule |
|---|---|
| Disease onset is later than the patient’s age, and both are known | Missing features expected at a later age are `not_yet_expected`, not mismatches |
| Onset or age is unknown | No age conclusion. Do not assume the patient is old enough |
| The disease is known for variable expression | Unmatched disease terms are expected. They are listed and not scored as evidence against the gene |
| Penetrance is incomplete or unknown | A phenotype conflict does not refute a variant. The conflict is shown. Penetrance is not estimated from one family unless a reviewed segregation analysis is supplied, and this module does not perform that analysis |
| A feature is explicitly excluded and is an obligate diagnostic criterion in a source the laboratory pinned | `possible_conflict` at minimum, and `conflict` if the criterion source says the feature is required. The criterion source is not HPO unless the pin says so |
| The same term can appear in many diseases | The match is non-specific. Information content, if computed, will be low. The term is still shown |

Variable expression and incomplete penetrance are properties of the disease record. If the record does not state them, the module does not invent a high or low penetrance to rescue a poor match.

## Deterministic methods that are allowed

Each method below may be implemented because the same pins and the same terms yield the same table. None of them may be the only stored result.

### Exact overlap

The intersection of patient-observed identifiers and disease-annotation identifiers. Transparent and incomplete. Two terms that are parent and child do not intersect. Exact overlap is reported first so the reviewer can see it before any ancestor logic.

### Ontology-aware overlap

The exact set, plus `patient_more_specific` and `patient_more_general`, labeled separately. This is the default comparison. It uses only the pinned parent-child graph.

### Information-content similarity

Optional. Computed per patient term against the disease set. The stored object is the list of (patient term, matched disease term or ancestor, information content), not the mean. A mean may be displayed only beside the list, and the formula name must be visible. A mean is not a diagnostic probability and is not comparable across ontology releases.

### Phenotype-set comparison

The four counts: specific overlaps, general overlaps, unmatched patient terms, unmatched disease terms. Excluded-term conflicts are a fifth count and are not folded into the unmatched count. These counts are the ranking facts.

### Contradictory phenotypes

Excluded patient terms that hit a disease annotation are listed individually. They do not subtract a hidden number of points from the overlap. A single specific conflict can matter more than several nonspecific overlaps. The reviewer sees the terms. The software does not decide that the conflict wins or that the overlap wins.

## How missing phenotype information changes ranking

| Phenotype state | Effect |
|---|---|
| No HPO terms | Phenotype rank is not computed. Document 95 sorts the remaining dimensions and badges every row `phenotype_not_supplied`. The module does not impute the classical features of a disease |
| Only broad terms | Ranking runs and is labeled low specificity. A gene must not rise to the top on a broad term alone if a more specific comparison exists for another gene |
| Some features not assessed | Those features are omitted from both the match and the mismatch lists |
| Free text only | No rank. The text may be stored for the reviewer and is not parsed into HPO by this module |
| Phenotype supplied for the proband and not for relatives | Only the proband is compared. A relative’s genotype is not given the proband’s phenotype |
| Secondary-findings analysis | Uses the secondary-finding policy’s gene-disease pairs, not the proband’s unexplained features, and only when the order includes that analysis. The phenotype section then says the indication phenotype was not the reason for inclusion |

Missing phenotype information lowers certainty. It does not lower a variant’s molecular evidence, and it must not be compensated by raising a similarity number.

## Ranking versus confirmation

The product of this stage is an order and an explanation. The explanation cites terms. The order is a review aid.

The stage does not:

- confirm a diagnosis
- select a single gene as the cause
- change a variant’s external classification
- convert a high overlap into pathogenic
- convert a low overlap into benign
- assert that the patient’s presentation is typical
- assert that an unmatched disease term was absent in the patient

A high overlap with weak variant evidence, and a low overlap with strong variant evidence, are both expected outputs. Document 95 says how they are displayed. Neither is discarded.

## Suggested default sort key, phenotype component only

The phenotype component of a later lexicographic sort may use this order, from more informative to less informative:

1. Conflict on a specific excluded term, which does not remove the row. It places a badge the reviewer must see. It is not a numeric penalty.
2. Count of `patient_more_specific` or exact matches.
3. Count of matches whose information content, if computed, is above a floor the configuration states. If information content is not computed, this key is skipped and the skip is recorded.
4. Presence of only `patient_more_general` matches.
5. `phenotype_not_supplied` or `phenotype_not_compared`, which sort after phenotype-supported rows and remain in the list.

Ties stay tied. They are not broken by a random or hidden weight.

## Failure conditions

| Failure | Result |
|---|---|
| HPO identifier fails the syntax check | That term is rejected. Other well-formed terms may be used. The rejection is listed |
| Ontology pin missing | No comparison |
| Term not in the pinned ontology | `unknown_term`. Not matched |
| Disease has no phenotype annotations | `disease_phenotype_not_curated`. The gene can still appear for non-phenotype reasons |
| Annotation source mixes diagnostic criteria and literature case reports without a label | The comparison may run only if the pin accepts that mixture, and the report says the annotations are not diagnostic criteria |

## What a geneticist should be able to read

For each gene-disease pair in the review list: the patient terms that matched, how specific the match was, the patient terms that did not match, the disease terms that were not observed, the excluded terms in conflict, the terms not assessed, the age rule that was applied, the ontology version, and a sentence that the table is not a diagnosis.

That sentence is part of the specification, not optional wording.

## Relationship to existing tools

Exomiser, Phenomizer, LIRICAL, and similar programs already compute phenotype similarity. Document 98 treats them as optional external rankers. Their combined scores are not imported as this module’s rank. If a laboratory stores an external score, it is stored under that tool’s name and version, beside the term-level table, and it does not replace the table.

GA4GH Phenopackets can represent observed and excluded phenotypes. The schema was identified and not adopted. A Phenopacket may be an input or an export later, after a version is reviewed. The internal record is the table in this document.

## Sources and limits

- HPO term syntax and the parent-child structure are established properties of the ontology. The ontology file itself was not downloaded on 23 November 2026, so no release number is cited.
- Exomiser’s documentation, read at the 14.0.1 advanced-analysis page, says HPO identifiers should be as detailed as possible because they heavily influence phenotype matching. That warning is adopted here as a limitation of any similarity method, including a local one.
- The Phenopackets variation-descriptor page was identified. It was not used as a field-level specification.
- Strande and colleagues, 2017, is the gene-disease validity source. Phenotype overlap does not change those classes.

No similarity coefficient is calculated in this research pass.
