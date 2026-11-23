# 96. Candidate review interface requirements

Accessed 23 November 2026. This document specifies what a geneticist must be able to inspect for one candidate. It is an interface contract, not a screen design and not an implemented view.

The interface shows stored facts and named gaps. It does not complete missing facts. It does not show a precision the inputs do not have. A frequency with an allele count of two is shown as a count and a fraction, not as a polished risk. A phase bar without a method is shown as method unknown. A phenotype table is shown as terms, not as a percent match alone.

The candidate under review is one allele in one sample, or an explicitly linked pair when document 94 has grouped a possible recessive pair. The pair view is additional. Each allele still has its own view.

## Always visible identity

| Item | Display | If absent |
|---|---|---|
| Sample token | The opaque `sample_id` | The view does not open |
| Assay | `assay_id` and `assay_version` | The view does not open |
| Genome build | GRCh37 or GRCh38 | The view does not open. No coordinate is shown as if the build were known |
| Contig and position | Original and normalized | Both. If normalization failed, the original is shown and the candidate is marked `ambiguous_variant` |
| REF and ALT | Original and normalized, including the ALT index if the record was multiallelic | Required |
| Variant class | SNV, indel, multi-nucleotide, symbolic SV, breakend, mitochondrial | Required. A wrong class label is a defect |
| rs identifier | Only if present in the file or returned by a pinned database | Blank. Not looked up from memory |
| Caller | Name and version when known | `not_stated` |

Coordinates are labeled with the build in the same field group as the numbers, so a position cannot be copied without its assembly.

## Transcript and nomenclature

| Item | Display |
|---|---|
| Transcript policy | MANE Select, a named accession, or `transcript_not_selected` |
| Transcript accession and version | For every transcript the view uses. A coding HGVS string without a version is not shown as HGVS. It is shown as an incomplete string |
| HGVS coding and protein | As emitted by the pinned annotator. The annotator name and version sit next to the string |
| Gene symbol | From the annotator, with the gene identifier if one was returned |
| Other transcripts | A disclosure when consequence or HGVS differs. Discordance is not collapsed to the first transcript |
| Exon or intron | As the annotator reports it, with the numbering source |

The interface does not let a user edit the HGVS string in place and keep the old provenance. An edited label is a reviewer note, stored separately.

## Zygosity, phase, and quality

| Item | Display | Uncertainty rule |
|---|---|---|
| Zygosity | The GT value and the words heterozygous, homozygous, hemizygous, two-alternate, or no-call | The words must match document 90. They are not loosened |
| Phase | Unphased, method unknown, or method named, plus cis, trans, or not established | A vertical bar alone is “caller-marked phased, method unknown” |
| Phase span | The bases or the parental transmissions that support it | If the span does not cover the pair, the pair is not described as phased |
| Sample depth | FORMAT DP | “Depth not provided.” Site DP is labeled site-level if it is shown at all |
| Allelic depths and fraction | AD or the caller-specific equivalent | The fraction is printed with the counts. No fraction is computed from nothing |
| Genotype quality | GQ if present | “Genotype quality not provided” |
| FILTER | The token and the header description | `.` is “filters not applied,” not PASS |
| Difficult-region badge | From document 91 and the laboratory mask | “No difficult-region mask was supplied” when that is true, plus any locus-level warning that document 91 always applies |
| Imbalance | The fraction and a review flag | Never the word mosaic unless a reviewer wrote it |

Quality numbers are not color-coded as pass unless the laboratory rule passed. Unassessed is a visible state, not a neutral gray that looks like a pass.

## Gene and disease context

For the condition under review, and separately for any other condition that has an assertion:

- gene-disease validity label, curator, and curation version
- inheritance label
- mechanism label, or `not_stated`
- whether the gene is on the laboratory’s secondary-findings list, and whether this order included that analysis
- a short statement that validity is not a variant class

If no disease was curated, the interface says the gene is not curated in the pinned source. It does not say the gene has no disease relationship.

## Consequence, frequency, and classification

Consequence uses the groups and the limitations in document 92. The selected consequence and the discordant ones are both shown. Prediction scores, if enabled later, appear in a section labeled prediction, with tool and version, and without a criterion code.

Frequency shows count, allele number, filtering allele frequency if the release defines it, homozygous count, the ancestry group of the highest frequency, the exome-versus-genome discordant flag, and the release name. The credible-maximum comparison shows every parameter or says it did not run. The interface must not round a very small frequency into “novel.” Novelty, if the word is used, is defined on the page as “no match in release X under the normalization rules,” which is not a clinical claim.

External classification shows each matching assertion: condition, significance, review status, date, germline or somatic if known, and release. Conflicts are shown side by side. The laboratory class is an empty field until a named reviewer writes it. The empty field is labeled “not classified by this laboratory,” not “VUS” and not “awaiting automatic classification.”

## Evidence for and against

The view has two lists that can both be non-empty.

Supporting observations may include: a condition-matched external assertion, a specific phenotype overlap, a mechanism-consistent consequence, transmission consistent with the stated mode, a frequency compatible with a stated model. Each item cites the dimension and the source.

Contrary or limiting observations may include: a conflicting assertion, a benign assertion for this condition, a frequency above the stated model, a specific phenotype conflict, an inheritance incompatibility, a difficult region, missing phase, missing parents, a transcript disagreement, a discordant frequency flag, and an assay class that was not validated.

Neither list is ranked by persuasion. Neither list is allowed to be empty-by-omission. If there is no contrary item, the view says “no contrary item is stored,” which is not the same as “no contrary evidence exists.”

Primary literature is shown as identifiers the curator or the database supplied. The interface does not summarize a paper that was not stored. It does not generate a narrative that adds facts.

## Phenotype and inheritance panels

The phenotype panel is the term table from document 93: matched, more general, unmatched patient terms, disease terms not observed, excluded conflicts, and not assessed. Ontology version is in the panel header. If phenotype was not supplied, the panel says so and does not show a suggested phenotype.

The inheritance panel states the mode, the zygosity, the parental samples used, the phase method, and the exact sentence document 94 allows. Apparent de novo and phase-unknown compound-heterozygous pairs use those words. The panel lists the conclusions that were not assessable.

## Assay limitations and missing data

A fixed box on every candidate contains:

- variant classes the assay did not validate
- whether coverage of the relevant gene was complete by the laboratory’s rule, or was not assessed
- difficult-region status for this locus
- confirmation policy: confirmed, not confirmed, or `not_stated`
- the missing-data list from document 95

The box is present for clean calls too. A clean call is not an occasion to hide the assay’s other limits.

## Why this row is on the list

The view shows the sort configuration and the keys that placed the row. It shows keys that were skipped. It does not show a score. A one-sentence template is permitted if it is filled only with those keys, for example: “On the default list because the call met the laboratory quality rule, the gene-disease curation is Definitive for the stated condition, and two patient terms are more specific than the disease annotation. Frequency was not compared. Parents were not tested.”

The template is forbidden from adding “therefore likely causal” or any clause the keys do not say.

## Provenance

Every external fact on the view carries source, version or date, and the match method (normalized allele, transcript, condition identifier). Facts without provenance are rendered in an unverified section and are excluded from the sort. The reviewer can see that section so unverified pre-annotation in the VCF is not invisible.

Reviewer notes, reviewer classification, and the automatic record are visually separate. Saving a note does not alter the automatic record.

## Uncertainty and false precision

The interface follows these display rules.

- Missing values are the words specified in this series, not blanks that could be read as normal, and not zeros.
- Fractions show the numerator and the denominator.
- Ranges stay ranges. A confidence interval is not replaced by its center.
- Phase, de novo, and compound heterozygosity use the qualified phrases in document 94.
- No control, gauge, or percentage represents “probability this explains the patient.”
- No green status means “benign” unless a reviewer classified it and the view attributes the classification to that reviewer.
- Counts of supporting items are not shown as a total score. The items themselves are shown.
- Rounding is allowed for display of long fractions only if the full fraction is available in the same view.

## Actions the interface may offer

| Action | Who | Effect |
|---|---|---|
| Include in the draft, exclude from the draft, or hold | Reviewer | A reviewer event. The automatic list is unchanged |
| Record a laboratory classification and a reason | Reviewer | Writes `human_classification`. Does not rewrite ClinVar |
| Open the audit row for a filtered-out variant | Reviewer | Read-only |
| Change the sort configuration | A configured laboratory role, not an ad hoc click on one case | A new configuration identifier. It does not edit old results |
| Export the candidate | Reviewer | The export contains the same gaps and provenance |

The interface does not offer “auto-classify,” “accept ClinVar,” or “mark gene negative.”

## Accessibility of the refusal states

A geneticist must be able to reach, from the candidate list, the rows that were not listed: low quality, not in class, deprioritized for frequency, and expanded-view-only consequence groups. Those rows use the same identity and provenance fields. Otherwise the default list becomes the only result, which this specification forbids.

## What this interface is not

It is not a variant interpretation worksheet that assigns PVS1 or any other criterion code. A laboratory may do that work beside this view. The codes, if recorded, are reviewer data and must cite the recommendation version the reviewer used. The software does not suggest a code.

It is not a clinical note to the patient. Wording for patients is out of scope.

## Sources

Local contract, constrained by documents 89 through 95. No interface was built and no usability test was run.
