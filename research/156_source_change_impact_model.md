# 156. Source change impact model

Accessed 23 November 2026. A source update produces an impact list. The list does not change a published rule by itself. Historical signed reports stay on the snapshots they cited.

## Dependency edges

An edge is stored only when a real citation exists. A gene symbol in a free-text paragraph is not an edge until a claim is linked.

| From | To |
|---|---|
| Snapshot record | Normalized external entity |
| External entity | Evidence claim |
| Evidence claim | Internal allele, variant, gene, drug, disease, or term |
| Claim | Rule, if a reviewer created one |
| Rule | Published interpretation or report template |
| Published report | The snapshot ids it rendered |

The reverse walk is the impact query: from a changed external record, to claims, to rules, to publications. Document 79 already requires this direction. The current staging tables can find a ClinVar variation id or a CPIC recommendation id. They cannot find the signed report that quoted it, because reports do not store snapshot ids.

## Change classes

| Class | Meaning | Typical result |
|---|---|---|
| `informational` | A field changed that no rule reads, or a new record matches nothing | Record the diff. No review, unless the registry says every new clinical assertion is reviewed |
| `rereview` | A cited assertion, function, validity label, or recommendation text changed | Queue the claims. The published rule stays as it was |
| `revalidate` | A rule’s input definition changed: allele contents, transcript version, phenotype bin, or ontology term the rule names | The rule cannot be newly published until the test or the reviewer rechecks it. The old publication stays current for already signed work |
| `block` | The license, a takedown, or a broken identity makes use unsafe | New publication that would cite the record is blocked. Existing signed reports are handled by the takedown rule in document 152 |
| `history_only` | The change is real and the signed report must not be rewritten | Always true for signed reports. Listed so it is not forgotten when another class also applies |

A new record can be `informational` and still be worth a reviewer’s attention. The class is about what is already published, not about whether the record is interesting.

## Worked impacts

| Update | Walk | Class |
|---|---|---|
| New ClinVar assertion on a variant with no internal claim | Stop at the external entity | `informational`, and the registry may still queue new pathogenic or conflicting aggregates for the local gene panel |
| ClinVar aggregate changes on a variant a claim quotes | Claim, then any rule and report that cite it | `rereview`. If the claim was used as a classification input, `revalidate` |
| ClinVar condition list changes while the significance string stays | Current hash misses it | After the hash includes the condition fields, this is `rereview` |
| PharmVar definition adds a variant to a star allele a rule names | Allele entity, phenotype rule, diplotype callers | `revalidate`. Blocked today because PharmVar is not licensed and the definition is not linked |
| New CPIC guideline version changes a phenotype boundary | Recommendation claim, phenotype rule, report wording | `revalidate`. The warfarin empty extract shows the opposite problem: a missing refresh must not be stored as “no recommendation” |
| CPIC recommendation text changes and the phenotype bin does not | The recommendation claim | `rereview` |
| New HPO release obsoletes a term used in a saved comparison | The comparison and any rank that cited the term | `history_only` for signed reports. `revalidate` for a ranking configuration that says it tracks current HPO |
| MANE replaces a transcript version used in stored HGVS | Every HGVS claim on that accession | `revalidate` for new annotation. Old HGVS remains true for the old version |
| gnomAD release changes an allele count a report quoted | The frequency observation | `informational` unless a frequency screen with stored parameters would change a deprioritization. Then `rereview`. It is not a reclassification |
| HGNC withdraws a symbol the panel matcher uses | Gene identity and the ClinVar alias filter | `revalidate` the matcher. Do not auto-rename claims |
| FDA table row edited on the website | The regulatory statement | `rereview`. The old snapshot remains the one a dated report cited |
| License change or a publisher takedown | Every shipped artifact of that source | `block` for new shipment |

## Customers and interpretations

The repository has no customer registry. This specification does not invent one. The impact list can name published interpretation versions. It cannot name a customer until a deployment records which publication version it runs. That record is an operational requirement of a later deployment, not a table to build in this task.

A local single-user knowledge base is affected when its published version cites the changed claim. Unpublished staging rows are affected when their snapshot id matches. Draft reviews that are still `pending` are recomputed from the new snapshot and keep the old queue item as history.

## What must not happen

- A new ClinVar class overwrites a reviewer’s classification.
- A new CPIC file changes a signed report’s sentence.
- A frequency change flips a variant from one ACMG class to another. This system does not assign those classes.
- An ontology update rewrites historical HPO codes.
- A failed or empty refresh, such as the warfarin recommendation endpoint, deletes the previous recommendations.
- An impact job publishes the result of the revalidation. It only blocks or queues.

## States a reviewer sees

| State after impact | Reader’s meaning |
|---|---|
| No publication cites it | Informational diff |
| A publication cites it and the cited field changed | Needs review. The publication is unchanged |
| A rule’s definition changed | New publication is blocked until revalidation |
| License or takedown | Shipping is blocked |
| Signed report | Still renders from its original snapshots |

## Recommendation

Wire the impact walk to snapshot diffs for ClinVar and CPIC first, because those diffs can already be computed once the raw body is kept. Include condition fields in the ClinVar comparison so a conflict change is visible. Leave PharmVar, HPO, and gnomAD impacts specified and unbuilt until those files are legally and technically pinned.
