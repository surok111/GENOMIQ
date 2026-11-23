# 90. VCF input contract

Accessed 23 November 2026. This is the input contract for the workflow in document 89. It is a local specification constrained by the VCF specification. It is not a parser and not a statement that any current GenomIQ file meets the contract.

The VCF text read for this pass is VCFv4.5, dated 25 February 2026, samtools hts-specs printing e821e4f. The VCFv4.3 page inspected on GitHub states that 4.3 is superseded by 4.4 and 4.5. Common clinical files are still 4.2 or 4.3. A future parser must name the versions it has been tested against. This research pass does not test one.

Callers do not emit the same INFO or FORMAT keys. GATK, DeepVariant, DRAGEN, and other callers were not compared file by file in this pass. The contract therefore separates fields the VCF specification requires from fields a clinical interpretation requires and from fields that are frequently absent.

## Requirement words

| Word | Meaning |
|---|---|
| Mandatory | The run stops, or the record is `rejected_input`, if the field is missing or malformed |
| Conditional | Required only when a named later conclusion is requested. If it is missing, that conclusion is not made |
| Optional | Stored when present. Absence does not by itself reject the record |
| Unavailable | Often missing from real VCFs. The contract must tolerate absence without inventing a value |
| Local | A GenomIQ rule. It is not a VCF-specification requirement |

Document 62 already makes genome build mandatory for any coordinate and forbids treating a missing filter as a pass. This contract keeps those rules.

## File-level contract

| Item | Requirement | If missing or wrong |
|---|---|---|
| `##fileformat` as the first line | Mandatory. Allow-list is an implementation decision. Versions that may be considered are 4.2, 4.3, 4.4, and 4.5. 4.1 and earlier are out of the initial allow-list unless a later validation adds them | `rejected_input` |
| Header line with the eight fixed columns in order: CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO | Mandatory | `rejected_input` |
| FORMAT and sample columns | Conditional for any genotype conclusion. A sites-only file can be stored as annotations and cannot support a zygosity or a negative result | Genotype-dependent stages do not run |
| Unique sample column names | Mandatory when sample columns exist | `rejected_input` |
| `##contig` or an equivalent contig dictionary | Local, mandatory before interpretation. The VCF specification recommends contig tags and requires them for BCF. A clinical file without them is not interpretable here | `rejected_input` |
| `##reference` or a separately supplied FASTA identifier | Local, mandatory. The header URI alone is not a build | `rejected_input` if the laboratory metadata also lacks `genome_build` |
| `##FILTER` definitions for every FILTER token used | Mandatory when a token other than PASS or `.` appears. The specification requires defined filter IDs | Record `rejected_input` if an undefined fail token is used to justify a quality decision |
| `##INFO` and `##FORMAT` definitions for every key used | Mandatory for keys the module interprets. Unknown keys are retained as uninterpreted text | Do not apply a meaning from another caller |
| Assembly metadata `GRCh37` or `GRCh38` | Local, mandatory, from laboratory metadata. `hg19` and `hg38` are not accepted as synonyms without an explicit alias policy | `ambiguous_variant` for every coordinate, as in document 62 |
| One assembly per file | Local, mandatory | `rejected_input` |

`##fileDate`, `##source`, and caller version lines are optional. When present they are stored. When absent the caller is `not_stated`. A missing caller version does not reject a laboratory genotype. It does block any conclusion that depends on a caller-specific annotation.

## Fixed record fields

| Field | VCF rule, as specified | Local clinical rule | If unusable |
|---|---|---|---|
| CHROM | Contig identifier | Must match the contig dictionary after the alias table | `rejected_input` for that record |
| POS | 1-based position of the first base of REF | Must be an integer inside the contig length | `rejected_input` |
| ID | Semicolon-separated identifiers or `.` | Optional. An rs identifier is supporting evidence of identity and is not sufficient. One rs can name more than one alternate allele | Do not invent an rs identifier. Do not join records on rs alone |
| REF | Reference bases | Must match the pinned FASTA after normalization checks. Comparison is case-insensitive for ACGTN | `ambiguous_variant` if the base does not match |
| ALT | Comma-separated alleles, or `.` when there is no alternate | Each allele is a sequence, a symbolic allele `<ID>`, or a breakend. Empty ALT is rejected | `rejected_input` |
| QUAL | Phred-scaled quality or `.` | Optional at the file level. `.` means missing, not zero | Do not threshold QUAL unless the laboratory supplied a rule for that caller |
| FILTER | PASS, a semicolon-separated fail list, or `.` | PASS means the caller’s filters passed. `.` means filters were not applied. A fail token means the named filter failed | `.` is `quality_unassessed`. A fail token is `low_quality` only under the laboratory’s rule for that token |
| INFO | Semicolon-separated key-value pairs, or `.` | Keys are interpreted only when defined in the header and listed in the caller profile | Undefined keys stay uninterpreted |

## Allele representation

REF and ALT use A, C, G, T, and N. The specification also allows symbolic alleles and breakend strings. Structural symbolic alleles include forms such as `<DEL>`, `<DUP>`, `<INS>`, `<INV>`, and `<CNV>`. The exact set accepted is the set defined by the declared VCF version plus the caller profile. An unknown symbolic allele is `not_in_validated_class`, not a small variant.

Normalization, local and conditional for any database comparison:

- Left-align indels against the pinned FASTA.
- Use the parsimonious representation, without a shared base that is not required and without an untrimmed repeat.
- Store the original POS, REF, and ALT beside the normalized form.
- Do not compare an unnormalized allele to a normalized catalog.

The VCF specification’s later versions describe this representation. The comparison key is still a local rule because files in the wild are not consistently normalized. A future implementation must name the normalizer and the FASTA. This pass does not.

Multiallelic records. One ALT cell may contain several alleles. Genotype indexes point at those alleles: 0 is REF, 1 is the first ALT, 2 is the second. Decomposition for annotation is allowed only if each child row records the parent record and the ALT index. Annotation of a multiallelic site as if it were biallelic is a failure. Splitting does not create phase between the alleles.

Multi-nucleotide substitutions. An ALT of the same length as REF, with more than one base changed, is one allele. It must not be silently split into SNVs for classification. A consequence annotator may show per-base effects. The review surface must show that those effects belong to one allele.

gVCF. A symbolic allele such as `<*>` or `<NON_REF>`, and a reference block with an END tag, describe a span where the caller did not call an alternate. They are not variants. They are conditional evidence of interrogation only when the laboratory’s gVCF profile says how reference blocks represent coverage. A variants-only VCF has no such spans. It cannot support `not_detected`.

## Chromosome naming

Accepted primary contigs, after aliasing, are the autosomes, X, Y, and the mitochondrial contig, on the declared build.

| Issue | Rule |
|---|---|
| `1` versus `chr1` | Alias only through the declared table. Do not guess from the first record |
| `M`, `MT`, `chrM` | Alias only through the table for that build. GRCh37 and hg19 are not interchangeable at the mitochondrial contig. The alias policy must say which mitochondrial sequence was used |
| Unplaced, unlocalized, decoy, and ALT contigs | Not interpreted as primary clinical coordinates unless the assay has a written rule. Store them as `not_in_validated_class` |
| HLA and other alternate haplotypes attached as extra contigs | Not a genotype on the primary chromosome. Do not merge them into the primary locus without a named method |

A variant on an alternate contig and a variant on the corresponding primary locus are different records until a reviewed mapping says otherwise.

## Genotype representation

GT is conditional and locally mandatory before any zygosity is shown.

| GT pattern | Meaning the module may store | Forbidden reading |
|---|---|---|
| `0/1` | Unphased heterozygous | Not phased |
| `0\|1` | Caller asserts phase | Not a known phase method. See below |
| `1/1` | Homozygous alternate for ALT index 1 | Not a statement about an unseen second site |
| `1/2` | Heterozygous for two alternate alleles | Not two independent records and not known to be in trans |
| `./.` or `.` | No-call | Not reference |
| Haploid `1` on X, Y, or MT | Hemizygous or haploid call, only if ploidy is expected for that contig and the reported karyotype | A haploid call on an autosome is `ambiguous_variant` |
| Missing GT cell | No genotype | Not reference |

Phasing. The vertical bar means the caller marked the genotype phased. It does not say whether the phase came from reads, from a trio, or from a population panel. Local rule: a cis or trans conclusion also requires a phase-method field. If the bar is present and the method is absent, the state is `phase_method_unknown`. Population or statistical phasing is not observed phase and cannot establish compound heterozygosity.

Ploidy. The module does not infer karyotype from GT. If the laboratory reports XY and the file shows heterozygous calls on non-pseudoautosomal X, the record is a QC flag, not a corrected karyotype. Pseudoautosomal regions need an explicit interval list before X and Y calls there are interpreted. That list was not compiled in this pass.

## Depth, allelic depth, and genotype quality

These fields are not required by the VCF specification. They are conditional for quality assessment.

| Field | Usual location | Local rule | If absent |
|---|---|---|---|
| Sample depth | FORMAT `DP` | Use this, not INFO `DP`, for a sample conclusion. INFO `DP` is often the site total across samples | `quality_unassessed` if the laboratory rule needs depth. Do not copy a default |
| Site depth | INFO `DP` | Optional context. Must not be labeled as the sample depth | Leave blank |
| Allelic depth | FORMAT `AD`, Number usually R | Conditional for allele fraction, imbalance flags, and any mosaic or heteroplasmy claim | No allele fraction is computed. Imbalance is `not_assessed` |
| Approximate read depth of one allele | FORMAT `AD` components, or caller-specific `AO`/`RO` | Interpret only under that caller’s profile | Do not add GATK and FreeBayes fields together |
| Genotype quality | FORMAT `GQ` | Conditional. Phred-scaled. Compare only with the laboratory’s threshold | `quality_unassessed` |
| Genotype likelihoods | FORMAT `PL` or `GP` | Optional. Do not reduce them to a class | Store if a later reviewed rule uses them |
| Variant quality | QUAL | Optional and caller-specific | Do not apply a universal QUAL cutoff |

Allelic imbalance. If AD is present, the module may display the alternate fraction. A departure from roughly equal fractions in a heterozygous diploid call is a review flag. It is also the expected pattern of mosaicism, of copy-number change, of capture bias, and of homologous misalignment. The flag must not be labeled mosaic and must not be labeled artifact unless the laboratory rule says so. Document 62 already forbids inferring mosaicism from a heterozygous fraction.

No universal depth is stated here. The ACMG 2021 standard says a minimum of Q20 and 10× has been suggested for germline heterozygous bases, that 10× is not always sufficient, that exome and genome mean depths used to reach a percent-covered target are assay-dependent, that mosaicism at 10–15 percent may need on the order of 30–50×, and that mitochondrial heteroplasmy near 5 percent needs still higher depth. Those are illustrations from that standard, not cutoffs for GenomIQ. The contract stores the laboratory’s numbers. If the laboratory does not supply them, depth is displayed and no pass/fail depth decision is made.

## Filter fields

| Token | Stored meaning |
|---|---|
| PASS | Caller filters passed for this record. Not a statement that the call is clinically true |
| `.` | Filters not applied |
| Any other defined token | The named filter failed or was flagged, using the header description |
| Sample-level `FT` | Used when the caller profile defines it. Site FILTER and sample FT are different. One must not be copied into the other |

Strand, mapping, and position-bias annotations (`FS`, `SOR`, `MQ`, `MQRankSum`, and similar keys) are unavailable in many files and are caller-specific even when present. They are optional. A threshold for them is valid only inside the caller profile that defines them. Absence is not a statement that the read evidence was balanced.

## Phase and family fields

| Field | Requirement | If absent |
|---|---|---|
| GT separator `/` or `\|` | Read from GT | Unphased if `/`. Method unknown if `\|` and no method field |
| Phase set (`PS`) or equivalent | Conditional for grouping phased variants | Variants are not placed on one haplotype |
| Pedigree | Optional file, not a VCF field | `family_not_supplied`. No de novo and no transmission conclusion |
| Mendelian tags emitted by a caller | Optional and caller-specific | The module may recompute consistency from parental GT. It does not treat a missing parent as reference |

## Copy-number and structural records

A clinical conclusion from these records is conditional on the assay having validated that class. Document 91 gives the capability limits. The file contract is:

| Representation | Minimum fields before the record is even displayable as that class | If incomplete |
|---|---|---|
| Symbolic deletion, duplication, inversion, insertion, or CNV | ALT symbolic allele, INFO `SVTYPE` or an equivalent defined key, and END or SVLEN | `ambiguous_variant` for structure. Do not guess the span |
| Imprecise breakpoint | The specification’s imprecise flag when the caller uses it, plus confidence interval fields if present | Breakpoints are stored as imprecise. They are not base-exact |
| Breakend | The breakend ALT syntax and a mate when the caller claims a paired event | An unpaired breakend is not a completed rearrangement |
| Copy-number integer | FORMAT `CN` or a defined equivalent, with the caller profile | A change in read depth is not stored as a copy number |
| Small indel in REF/ALT sequence | Ordinary allele fields | This is not a CNV and is not evidence that exon-level CNVs were examined |

Many callers emit different SV INFO keys. Keys that are not in the header and the caller profile stay uninterpreted. Two SV records with similar spans are not the same event without a named comparison rule. This contract does not define that rule.

## Mitochondrial records

Conditional. The mitochondrial contig must be in the assay scope.

| Issue | Rule |
|---|---|
| Diploid GT such as `0/1` on the mitochondrial contig | Not accepted as a heteroplasmy result. Store the genotype as representation-invalid for mitochondria and do not convert it to a fraction |
| Allele fraction | Conditional for any heteroplasmy statement. Source field must be named | If absent, heteroplasmy is `not_assessed` |
| Depth | Compared only with the laboratory’s mitochondrial limit of detection | Below the limit, or no limit stated: `quality_unassessed` |
| NUMT | Not detectable from the VCF alone | The review surface says short-read mitochondrial calls can be nuclear inserts. It does not adjudicate them |

## Sample identifiers

The sample column header is the only identity inside the VCF. Local rule: it must match `sample_id` or a supplied crosswalk. Headers that look like names, accessions, or medical-record numbers are not interpreted as those objects. This research contract uses opaque tokens, consistent with document 62. No patient name is an input.

A multi-sample file is a set of samples, not a family, until a pedigree says so.

## Missing and incomplete annotation

Consequence, ClinVar class, gnomAD frequency, HGVS, and gene symbols are not VCF-required fields. They are often added later by an annotator. If they are already inside INFO:

- Store them with the INFO key name.
- Do not trust them unless the header or the laboratory metadata gives the annotator name, version, transcript set, and frequency release.
- A pre-annotated CSQ or ANN field without that provenance is `annotation_unverified`. It may be shown as text. It must not drive a filter.
- Overwriting a pre-existing annotation with a new annotator is allowed only if both copies are kept and the new one is the pinned run.

| Annotation | Typical availability in a caller VCF | Contract |
|---|---|---|
| Gene symbol | Unavailable | Produced later, or unverified if pre-annotated |
| Transcript and HGVS | Unavailable | Conditional for any HGVS display. Version required |
| Consequence term | Unavailable | Conditional for a consequence filter |
| Population frequency | Unavailable | Conditional for a frequency comparison |
| ClinVar class | Unavailable | Optional annotation. Never a mandatory input |
| Depth and GT | Often present, not guaranteed | As above |
| Phase method | Unavailable | `phase_method_unknown` when phase is claimed |
| Phenotype | Not a VCF field | Separate metadata. Absence does not reject the VCF |

## Acceptance outcomes

| Situation | Outcome |
|---|---|
| Well-formed allowed version, build known, samples bound, REF consistent | Record may enter QC |
| Genotype present, filter `.`, no depth | Enter annotation. Quality disposition `quality_unassessed`. No pass |
| Genotype absent | `no_call` |
| Structural record and the assay did not validate SV | `not_in_validated_class`. The record remains visible in the limitation and audit sections |
| Pre-annotated clinical class without a version | Shown as unverified text. Not used for prioritization |

## Fields this contract deliberately does not require

A BAM path. A read-level pileup. Somatic fields such as tumor-normal status. A clinical diagnosis. A populated INFO clinical key. A pedigree. An HPO list. A specific caller.

A germline constitutional workflow rejects a file the laboratory has marked as tumor or cell-free DNA, because document 62 already separates germline and somatic. The rejection reason is `not_applicable` for this workflow, not a failed genotype.

## Sources

- VCFv4.5 specification, 25 February 2026, https://samtools.github.io/hts-specs/VCFv4.5.pdf, printing e821e4f. Confirms the required fileformat line, the eight fixed columns, INFO and FORMAT header structure, genotype ordering, symbolic and breakend representations, and the recommendation that contig and reference tags be present.
- VCFv4.3 source header inspected on GitHub, which points readers to 4.4 and 4.5.
- Rehder and colleagues, Genetics in Medicine, 29 April 2021. Coverage examples cited above are illustrations from that standard, not local thresholds.
- Document 62. Build, filter, zygosity, phase, and negative-result rules reused rather than relaxed.

The contract does not certify that a file which satisfies it is analytically valid. Analytical validity remains the laboratory’s validation of the assay that produced the file.
