# 92. Variant filtering strategy

Accessed 23 November 2026. This document specifies a staged, configurable filter for the workflow in document 89. It is a display and audit policy. It is not a classifier and not an instruction to delete variants.

Four layers are kept separate because they answer different questions.

| Layer | Question | What a “remove” action is allowed to mean |
|---|---|---|
| A. Technical | Is this call usable under the laboratory’s rules? | The call is `low_quality` or `quality_unassessed`. It is not benign |
| B. Frequency | Is the allele too common for a fully specified disease model, or is the frequency simply being shown? | Deprioritize or hide from the default view. The row remains in the audit. Frequency is not a classification |
| C. Consequence | What does the pinned transcript set say the allele does? | A consequence filter may hide a class the laboratory chose not to review first. It does not mean the hidden class is harmless |
| D. Clinical evidence | What have external sources asserted, and do they agree? | Annotations and conflict flags. They do not set the laboratory class |

A layer that cannot run records a not-assessed state. It does not borrow a threshold from another layer.

The default configuration is conservative: technical failures leave the default candidate view, and biological filters deprioritize rather than drop, until a named laboratory configuration says otherwise. A configuration is a versioned object. A result stores the configuration identifier. Two configurations are not one result.

## A. Technical filtering

Purpose. Keep calls that the laboratory’s own validation would accept, and quarantine the rest without describing them as reference.

Inputs. Document 90’s quality fields and the assay thresholds from document 62. No threshold is invented here.

| Check | Rule | Disposition if it fails | If the field is absent |
|---|---|---|---|
| FILTER token | A laboratory fail list. PASS is not a clinical truth | `low_quality` | `.` is `quality_unassessed`, not PASS |
| Sample depth | Compare FORMAT DP with the assay minimum | `low_quality` | `quality_unassessed`. No borrowed minimum |
| Genotype quality | Compare GQ with the assay minimum | `low_quality` | `quality_unassessed` |
| Genotype | GT required for a zygosity view | `no_call` | `no_call` |
| Strand, mapping, or position bias | Only the keys and cutoffs in that caller’s profile | `low_quality` when the profile says so | `not_assessed`. Do not treat absence as balance |
| Allelic fraction | Display. Apply a fail rule only if the assay wrote one for diploid heterozygous calls | Flag for review, or `low_quality` if the rule says so | `not_assessed` |
| Suspected artifact | Only a caller or laboratory flag that names the artifact | `low_quality` with the flag name | Do not infer an artifact from novelty or from a single-read allele |
| Difficult region | Document 91’s homologous, GC, or low-complexity flag, when the laboratory supplies a mask. Without a mask, only the named loci in document 91 are flagged | `held_for_review`. Do not auto-exclude | The absence of a mask is stated. It is not a statement that all regions are easy |
| Wrong variant class | Class not in `test_scope` | `not_in_validated_class` | The class is not interpreted |

Allelic imbalance is not, by itself, an artifact rule. Capture bias, homology, mosaicism, and copy-number change can all move the fraction. The row stays visible with the fraction printed.

A variants-only file produces no technical pass for sites that are not in the file. Those sites are not filtered as reference. They are absent, and negative language is blocked until coverage evidence exists.

What can be automatic. Comparisons with supplied numbers and tokens.

What needs a person. Any borderline fail the laboratory’s SOP sends to manual review. Any difficult-region pass.

What must not be inferred. A universal depth, a universal GQ, a universal allele balance, or a cleaned VCF that no longer contains the failed rows.

## B. Population frequency filtering

Purpose. Show how often the allele has been seen in a named resource, and apply a frequency screen only when the disease model is complete enough to support one.

### The comparison is not a universal cutoff

This specification rejects a single allele-frequency threshold for all genes and all diseases. It also rejects two shorthand readings:

- Common does not mean benign. A founder allele can be pathogenic and relatively frequent. A risk allele can be common and still not be the Mendelian cause under review. A frequency screen answers a stated model. It does not answer every clinical question.
- Rare does not mean pathogenic. Most rare alleles are not disease-causing. Absence from a database is not a functional result and is not a case report.

ACMG/AMP 2015 includes frequency criteria (BA1, BS1, PM2) that are applied by a laboratory during classification. Those criteria are not applied automatically here. ClinGen’s sequence-variant work, as summarized by Harrison, Biesecker, and Rehm in 2019, treats filtering allele frequency as a lower-bound estimate and expects disease-specific BA1 and BS1 thresholds. The same summary says that simply inverting a BS1 threshold to obtain PM2 is discouraged. This module therefore does not implement BA1, BS1, or PM2. It can display the counts a person would need in order to consider them.

### Frequency resource

gnomAD is the appropriate default reference when the assembly matches, because it publishes allele count, allele number, homozygous count, ancestry-group frequencies, and a filtering allele frequency. It is not the only legitimate resource. A laboratory may pin another reference. The pin must include the release and the assembly.

Facts retrieved for gnomAD:

- v4.0, announced 1 November 2023, is aligned to GRCh38. The announcement reports 807,162 individuals, with 730,947 exomes and 76,215 genomes. It also says the release contains more non-European ancestry than earlier releases and, because of cohorts such as UK Biobank, a higher European proportion than earlier releases. Both statements are about that release. Neither makes the resource representative of every patient.
- v4.0 uses a combined filtering allele frequency across exomes and genomes, and still exposes the separate values.
- v4.1, announced 19 April 2024, corrects allele-number handling and adds joint allele numbers across called sites. It also flags variants whose exome and genome frequencies are highly discordant. A discordant flag is a data-quality warning. It is not a benign or pathogenic label.
- v4 is not a control cohort cleaned of every disease. The v4.0 announcement says phenotype metadata are incomplete and disease subsets were not offered for that reason. Affected people can be present. Adult-onset disease is the clearest example.
- v2.1.1 is a GRCh37-era resource. It must not be applied to GRCh38 coordinates. This pass did not re-download v2.1.1.

Fields the frequency layer stores when the resource provides them:

| Field | Why it is separate |
|---|---|
| Allele count and allele number | A frequency with a count of 1 does not have the same stability as a frequency with a count of 100 |
| Filtering allele frequency, as defined by that release | A conservative bound. The module uses the release’s value. It does not re-derive the formula |
| Highest ancestry-group frequency and the group label | A global average can hide a higher frequency in one group |
| Homozygous and hemizygous counts | Relevant to recessive and X-linked questions. A rare allele that is often homozygous is a different observation from a rare allele seen once in heterozygotes |
| Exome-versus-genome discordant flag | Stops a combined frequency from looking cleaner than the callsets are |
| Coverage at the locus in the frequency resource | Absence of a variant from a resource that did not cover the base is not absence from the population |
| The patient’s stated ancestry, if the laboratory supplied it | Used only as a label for which group the reviewer may want to read. It is not inferred from the VCF |

### Maximum credible allele frequency

Whiffin and colleagues, Genetics in Medicine, 18 May 2017, define a maximum credible population allele frequency for a pathogenic allele from disease prevalence, the maximum contribution of one allele, and penetrance. Inheritance changes the arithmetic. Their dominant worked example also accounts for alleles per person. Their recessive example uses a different relationship between carrier frequency and affected prevalence. Genetic heterogeneity and allelic heterogeneity are inputs, not constants. They compare the result with a confidence-bounded allele count, not with a raw point estimate, because sampling variance is large for rare alleles.

Local rule. A frequency screen may fire only when all of the following are stored, each with a source:

- the condition being tested, not a generic “rare disease”
- prevalence
- inheritance mode
- penetrance used in the model, which may be a conservative bound rather than the true penetrance
- maximum genetic contribution and maximum allelic contribution, or an explicit statement that the model assumes a single allele explains the gene’s share
- the frequency resource, release, assembly, and which statistic is compared (filtering allele frequency or a named upper or lower bound)
- the ancestry groups included in the comparison

If any item is missing, the disposition is `frequency_not_compared`. The counts are still displayed. No row is hidden for frequency.

If the items are present and the chosen statistic exceeds the maximum credible frequency, the disposition is `deprioritized` under the default configuration, with the comparison stored. A laboratory configuration may instead use `excluded_by_rule`. Neither disposition writes Likely benign or Benign.

If the statistic is below the maximum, the disposition is `frequency_compatible_with_model`. That phrase is deliberate. It is not PM2 and not a point toward pathogenic.

### Ancestry and representation

A frequency from a group that does not include people similar to the patient is a weak observation. A frequency from a small group is a noisy observation. Whiffin and colleagues already note that a threshold becomes more conservative when allele number is small, and that a variant common in any one well-sampled group is unlikely to be a rare high-penetrance dominant cause if the disease architecture is similar in that group. The second point is a model, not a law. Founder effects are the counterexample the reviewer must still be able to see.

The module must not:

- assign the patient to a gnomAD ancestry group from genotypes
- treat “other,” “remaining,” or a group with a small allele number as equivalent to a large group
- hide a variant because it is common in a group and rare in the group that matches a stated ancestry, without showing both numbers
- use a frequency screen to decide that a recessive allele is benign in the heterozygous state. Carrier frequency is expected for recessive disease. The homozygous count and the second allele are the relevant observations, and they still do not finish the classification

### Penetrance, prevalence, and heterogeneity

These three parameters dominate the threshold. A lower penetrance raises the allele frequency that is still credible. A lower prevalence lowers it. A disease in which one allele explains most cases allows a higher per-allele frequency than a disease split across hundreds of alleles. Because the parameters are uncertain, the stored comparison includes the parameter values. A second comparison with different parameters is a different configuration, not a contradiction to be smoothed away.

The module does not estimate prevalence or penetrance from the VCF or from the patient’s phenotype.

## C. Functional consequence filtering

Purpose. Group alleles by what a pinned annotator says about a pinned transcript, and to keep the known failures of that grouping visible.

Inputs. Document 89 stage 7. A transcript policy. A consequence vocabulary from the annotator, typically Sequence Ontology terms. This pass did not re-download the Sequence Ontology. An implementation must pin the term set the annotator version actually emits.

Default display groups. These are review groups, not pathogenicity ranks.

| Group | Typical terms the group is meant to collect | Default display | Limitation that must be printed with the group |
|---|---|---|---|
| Predicted loss of function | Frameshift, stop gained, start lost, canonical splice donor or acceptor, transcript ablation, and exon-level deletions only when the assay validated them | Shown | Predicted. NMD, alternative splicing, and the gene’s mechanism decide whether loss of function is relevant. A stop near the end, or in an exon the transcript skips, is not automatically pathogenic. PVS1 is not applied |
| Missense and inframe indel | Missense, inframe insertion and deletion, protein-altering | Shown | Most are not pathogenic. A prediction score is not a group change |
| Canonical splice | Splice donor or acceptor at the dinucleotide | Shown, and also listed inside predicted loss of function if the laboratory groups them there | The dinucleotide is not a function study. Nearby nucleotides can be splice-affecting and are not this group |
| Splice region | The annotator’s splice-region term, outside the dinucleotide | Shown | The term is a window, not a prediction that splicing changed |
| Synonymous | Synonymous and stop-retained | Shown in an expanded view. Hidden from the default view only if the configuration says so, and never hidden when a splice annotation or a ClinVar assertion is present | Synonymous does not mean silent. Splice-affecting synonymous alleles are the reason for the exception |
| Noncoding transcript or UTR | 5′ UTR, 3′ UTR, noncoding exon | Expanded view, same exception rule | Effect is usually unknown. A known pathogenic UTR allele must not be hidden by this group |
| Intronic, beyond the splice region | Intron variant | Expanded view on a genome. On an exome, presence means the base happened to be captured or the call is suspicious | An exome that does not contain deep intronic calls did not test them |
| Regulatory and intergenic | Regulatory region, transcription-factor binding, upstream, downstream, intergenic | Expanded view | Consequence annotations here are weak. Hiding them is a review-scope choice, not a benign call |
| Other or no consequence | Annotator failed, or the term is not in the map | Shown as `consequence_unassessed` | Absence of a term is not “benign consequence” |

A variant with different consequences on different selected transcripts is `consequence_discordant`. It stays in the more severe group for display and the other consequences are listed. Severity for this sentence means the order of the table above, which is an order of molecular bluntness, not of clinical importance. A missense allele in a dominant gene can matter more than a stop in a gene where loss of function is not the mechanism.

Loss of function as a mechanism applies only where the gene-disease record says the disease is caused by loss of function. If the record says gain of function, or if the mechanism is `not_stated`, a predicted truncating allele is not ranked as supporting. It is ranked as mechanism-unknown.

Prediction tools such as SpliceAI, CADD, or REVEL may be stored later as optional annotations. Document 98 gives the conditions. They do not move an allele between groups in this specification. ClinGen’s calibration of computational evidence is version-specific and was not opened in this pass. No PP3 or BP4 rule is created.

What must not be inferred. That the selected transcript is the one the patient’s tissue uses. That MANE Select, when used, removes transcript disagreement. That a consequence group is an ACMG criterion.

## D. Clinical evidence filtering

Purpose. Attach external evidence so the reviewer can see agreement, silence, and conflict. Silence is a separate state from benign.

### ClinVar

Store, per assertion that matches the normalized allele:

- the condition, using the source’s identifier and name
- the clinical significance string
- the review status string
- the date last evaluated, when present
- whether the submission is germline or somatic, when present
- the release of ClinVar

Do not store a star count computed by this module. ClinVar’s review status is the source field. A familiar star display is only a rendering of that status, and the legend must come from the pinned release.

Conflict. If two assertions for the same allele and the same condition disagree, the flag is `evidence_conflict`. The conflicting strings are both shown. The module does not average them, vote them, or pick the more severe one.

A conflict across different conditions is `condition_specific_assertion`, not automatically a conflict. A pathogenic assertion for one phenotype and a benign assertion for another are both displayed. Neither is applied to a third phenotype.

An assertion with no assertion criteria, or with a conflicting review status, is shown and is not used as a display boost. An expert-panel or practice-guideline assertion is shown with that status and is still not the laboratory’s class.

ClinGen recommended discontinuing ACMG/AMP PP5 and BP6, the criteria that treated a reputable classification as evidence when the laboratory had not reviewed the primary data. The letter was published in Genetics in Medicine and is the PMC6709533 text read for this pass. This filter does not implement PP5 or BP6.

Absence from the pinned ClinVar release is `no_clinvar_assertion`. It does not change frequency or consequence.

### Gene-disease validity

The ClinGen framework published by Strande, Riggs, and colleagues in the American Journal of Human Genetics in 2017 uses Definitive, Strong, Moderate, Limited, No Reported Evidence, and Conflicting Evidence. Later SOP versions separate disputed and refuted evidence. The current SOP was not downloaded on 23 November 2026. An implementation must pin the SOP and the curation release.

| Stored label | How display may use it | Forbidden use |
|---|---|---|
| Definitive or Strong | Eligible for the default phenotype-related view if other gates allow | Not a statement that this variant is pathogenic |
| Moderate | Eligible, with the label visible | Not upgraded to definitive |
| Limited | Shown in an expanded gene view | Not hidden as if the gene were irrelevant, and not treated as established |
| Conflicting, disputed, or refuted | Shown with the conflict. Default view does not prefer the gene | Not deleted. A refuted curation is evidence against the gene-disease pair, not against every variant in the gene for every other disease |
| No reported evidence, or not curated | `not_curated` | Not a negative gene and not a license to interpret the variant in a new gene as diagnostic |

Gene-disease validity is about the gene and the disease. It is not a variant classification. A definitive gene can contain a benign variant. A limited gene can contain a true pathogenic variant that the curation has not yet established. The display keeps those layers apart.

### Guidelines and primary evidence

A practice guideline, a ClinGen expert panel, or a primary paper may be attached by identifier. The module stores the identifier, the condition, and a short quoted scope if a curator entered one. It does not derive a criterion code (PVS1, PS3, PP1, or any other) from the identifier. Criterion codes are a classification worksheet. This specification does not create that worksheet.

Primary evidence means the laboratory or the reviewer can see the paper, the segregation count, or the functional result. A citation without those data is a pointer. It is not the evidence itself.

### What clinical-evidence filtering may change

Under the default configuration:

- `evidence_conflict` stays in the default view
- an external pathogenic or likely pathogenic assertion for the condition under review is a display fact, not a sort weight that overrides quality failure
- an external benign or likely benign assertion for that condition deprioritizes the row and remains visible in the audit
- somatic, drug-response, and risk-factor assertions do not enter the Mendelian candidate view. They can appear in a separately labeled section
- no combination of ClinVar status and gene validity writes `human_classification`

A laboratory may tighten or loosen the default only by naming a new configuration. The configuration cannot contain the rule “ClinVar pathogenic means report as pathogenic.”

## How the layers combine

The default view includes a row when:

- it is not `low_quality`, `no_call`, `rejected_input`, or `not_in_validated_class`
- and it was not deprioritized by a frequency screen that actually ran
- and its consequence group is in the default set, or an exception in section C kept it
- and it is annotated for review

`quality_unassessed` stays in the default view and is badged, because hiding an unmeasured call would look like a pass.

Rows that fail a layer are counted by rule name. The report uses those counts. A count of excluded rows is not a count of benign variants.

## Configuration parameters that must be explicit

| Parameter | Default in this specification |
|---|---|
| Technical thresholds | None. Required from the assay before a pass/fail depth or GQ decision |
| Frequency resource and release | Required before any frequency display that is used in a screen. No screen without a complete disease model |
| Consequence groups in the default view | Predicted loss of function, missense and inframe, canonical splice, splice region, and any row with a condition-matched ClinVar assertion or a splice annotation |
| Gene-validity minimum for the default view | No minimum that drops Limited or not-curated rows from the audit. The default candidate view may sort Definitive and Strong first and must still be able to show the others |
| ClinVar vote | Not allowed |
| Automatic ACMG class | Not allowed |

## Sources

- Richards and colleagues, Genetics in Medicine, 2015, PMC4544753. The five-class framework and the existence of frequency and computational criteria. Not implemented here.
- Harrison, Biesecker, and Rehm, Current Protocols in Human Genetics, 2019, PMC6885382. Disease-specific frequency thresholds, filtering allele frequency as a lower bound, and the warning against inverting BS1 to make PM2.
- ClinGen SVI letter on PP5 and BP6, Genetics in Medicine, PMC6709533.
- Whiffin and colleagues, Genetics in Medicine, 18 May 2017. Maximum credible allele frequency and the role of prevalence, heterogeneity, penetrance, inheritance, and sampling variance.
- gnomAD v4.0 announcement, 1 November 2023, and v4.1 announcement, 19 April 2024.
- Strande, Riggs, and colleagues, American Journal of Human Genetics, 2017. Gene-disease validity classes.
- Documents 62 and 91. Assay thresholds and variant-class limits.

No frequency number in the Whiffin examples is adopted as a GenomIQ cutoff. The examples belong to the diseases and the ExAC snapshot in that paper.
