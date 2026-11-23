# 154. Source conflict management model

Accessed 23 November 2026. A conflict is a stored object. It is not a merge, a vote, or a preference for the newest release. Document 79 defined the outline. This document applies it to the disagreements this project has already met and to the ones the source audit expects.

## Conflict record

| Field | Content |
|---|---|
| Identifiers | The evidence or claim rows that disagree. At least two |
| Sources | Publisher, snapshot, and version of each side |
| Dates | Source release date and retrieval date of each side. Approval date if a person resolved it |
| Claims | The original statements, not a paraphrase that already chooses |
| Evidence type | Guideline, function table, regulatory table, aggregate assertion, submitter assertion, frequency observation, validity label, ontology edge, allele definition |
| Scope | Gene, allele, transcript, build, drug, condition, population, phenotype. A disagreement outside that scope is a different conflict or no conflict |
| Why they cannot be merged | The reason, from the closed list below |
| Status | `unresolved`, `distinguished`, `resolved_by_reviewer` |
| Resolution | Empty, or the reviewer’s decision and what it applies to. The losing statement is not deleted |

`distinguished` means the two statements are about different scopes and only looked like a conflict. Example: a pathogenic assertion for one condition and a benign assertion for another. They are both kept and linked as condition-specific, which document 92 already requires.

## Reasons that block a merge

| Reason | Meaning |
|---|---|
| `different_question` | Frequency versus classification, or validity versus variant pathogenicity |
| `different_scope` | Drug, population, transcript, build, or condition differs |
| `different_issuer` | CPIC and DPWG, or two ClinVar submitters |
| `aggregate_hides_parts` | One field summarizes records that disagree |
| `definition_changed` | The allele or transcript is not the same object |
| `secondary_reprint` | One side is a summary of the other and is not independent |
| `unversioned` | One side has no release and cannot be preferred |

None of these reasons selects a winner.

## Cases already in this project

| Case | Sides | Why it is not merged | Status today |
|---|---|---|---|
| ClinVar blended string on an rs summary | Document 31: one esummary clinical string contains disagreeing submitters | `aggregate_hides_parts` | Not used as function. The FTP ingest still stores one aggregate and drops the conflicting value unless it is exactly Pathogenic or Likely pathogenic |
| ClinVar `ClinicalSignificance` versus `ClinSigSimple` | README example: criteria-bearing benign submissions and a no-criteria pathogenic submission | `aggregate_hides_parts` | The hash ignores `ClinSigSimple`, so the disagreement is invisible |
| CPIC versus DPWG warfarin | CPIC algorithm and a reprinted DPWG percent table | `different_issuer`. The reprint is also `secondary_reprint` | Document 72 leaves them as two methods |
| DPYD activity 0.5 versus a 0.75 note | CPIC workbook value and a ClinPGx blog about an unpublished change | `different_issuer` and the blog is not a guideline | Document 74 keeps 0.5 as the database value and the blog as a note |
| NAT2 legacy names versus later cores | Local star names and a nomenclature change | `definition_changed` | Document 76. A written crosswalk was not shown |
| CYP2D6 1846 versus 1847 | Legacy page and PharmVar coordinate note | `definition_changed` | The legacy page is historical. It is not the current definition |
| Local RM/UM label versus CPIC Table 1 | One local token for two CPIC classes | Internal versus `different_issuer` | Document 60. Not implemented |
| FDA table versus CPIC dose | Table language and a guideline sentence | `different_issuer` and often `different_scope` | Document 74. Label PDFs were not opened, so the FDA side of a label conflict is `unversioned` |
| Empty ClinPGx phenotype objects on carbamazepine rows | The API extract does not say which HLA allele a sentence belongs to | `unversioned` scope | Document 20. The sentence is not assigned |
| ACMG 2013 MTHFR versus a local thrombophilia action | A negative testing recommendation and a local risk sum | `different_question` | The local sum is not an ACMG class |
| GRCh37 and GRCh38 rows | Two coordinates for one VariationID | `different_scope` | The parser keeps GRCh38 and drops the other. That is a data loss, not a resolution |
| gnomAD exome versus genome counts | Document 92, from the v4.1 announcement | `different_scope` until the discordant flag is stored | The flag is not in the current schema |
| ClinGen versus GenCC | Not yet loaded | `different_issuer` when labels differ | Expected. Do not average them |
| Ontology releases | A term replaced or a parent moved | `definition_changed` | Document 147. Old reports keep the old term |

## Cases the ingest must start recording

ClinVar conflicting submissions. When the aggregate is `Conflicting interpretations of pathogenicity`, or when `ClinSigSimple` and `ClinicalSignificance` disagree, the staging row is a conflict, not a drop and not a single class. Until SCV rows are stored, the conflict’s two sides are incomplete and the record says `parts_not_in_snapshot`. That is still better than discarding the row.

CPIC versus DPWG. Any future DPWG monograph is stored as its own guideline. A drug that has both stays `unresolved` for a merged dose. A reviewer may approve a rule that cites one issuer and names the other as not used. That is `resolved_by_reviewer` for that rule’s scope only.

Allele definitions. If a workbook snapshot and a later PharmVar snapshot list different variants for the same star name, the star name is not the key. Both definitions remain. Phenotype translation cannot run on that name until a reviewer binds the rule to one definition.

Transcript and assembly. An HGVS expression on `NM_000110.3` and one on `NM_000110.4` are not merged. A GRCh37 coordinate and a GRCh38 coordinate are not merged without a liftover snapshot, and liftover is not authorized.

Frequency. Two releases of gnomAD are two observations. A report cites the release it used. A large change between releases is an impact event, not an automatic reclassification.

Regulatory versus guideline. The FDA table and a CPIC sentence remain side by side. The report can show both. It cannot invent a sentence that satisfies both if they differ.

Gene-disease validity. ClinGen Limited and GenCC Definitive for the same pair are both shown. Phenotype ranking may prefer the stronger label for sort order, as document 95 does, and the sort does not delete the weaker label.

Ontology. Two HPO releases that disagree about a parent edge are both stored. A comparison uses the release in the report.

## Resolution rights

The software may set `distinguished` when the scope fields differ and a written rule says those fields split the question. Condition identifiers are such a field. Dates are not. A higher review status is not. A larger sample size is not.

The software must not set `resolved_by_reviewer`. A person does, and the decision records which scope it covers. A resolution for warfarin dosing does not resolve a DPYD activity value.

## What the review queue already does

`src/review_queue/policy.py` forces `pending` when the change type or the category is `conflict`, and also for recommendation text, evidence level, and clinical classification. That policy matches this model. It does not by itself create the conflict record. The ClinVar parser’s decision to drop non-exact pathogenic strings means many conflicts never reach the queue. Fixing that drop is a prerequisite, not a new clinical rule.

## Recommendation

Persist both sides, the snapshots, and the merge block. Leave status `unresolved` until a named reviewer writes a scoped decision. Do not add a numeric evidence score to break ties.
