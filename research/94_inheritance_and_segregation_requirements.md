# 94. Inheritance and segregation requirements

Accessed 23 November 2026. This document specifies which inheritance statements a deterministic module may make from genotypes, and which statements require parents, phase, or a laboratory finding the VCF does not contain.

Trio data are not assumed. A single-sample file is the normal case. The module must return a useful zygosity and compatibility statement for that case and must refuse de novo and cis/trans conclusions.

No pedigree and no patient genotype were used.

## Terms

| Term | Meaning in this specification |
|---|---|
| Compatible | The observed genotypes do not break the pattern, given the samples tested |
| Incompatible | The observed genotypes break the pattern, given the samples tested and the assumptions stated beside the conclusion |
| Not assessable | A required genotype, phase, karyotype, or inheritance label is missing. This is the correct result for most single-sample questions beyond zygosity |
| Apparent | A pattern that is suggested and not confirmed. Apparent de novo and apparent compound heterozygosity are the two uses |

Compatible is not a diagnosis. Incompatible is not a benign classification. A pattern can be incompatible with one inheritance mode and still be true under another mode, under mosaicism, or under a sample-identity error.

## Inputs

| Input | Single-sample use | Family use |
|---|---|---|
| Proband GT and the contig ploidy | Required for any statement | Required |
| Laboratory-reported karyotype | Required before an X-linked or Y conclusion | Required |
| Curated inheritance for the gene-disease pair | Required for a compatibility label. If it is missing, zygosity is shown and compatibility is `inheritance_not_stated` | Same |
| Parental samples in the same file or a linked file | Not required | Required for transmission and for de novo |
| Pedigree with mother and father identifiers | Not required | Required to know which columns are the parents. Column order is not a pedigree |
| Affected status of each relative | Not required | Optional. Unknown stays unknown. The PED code for unknown must not be read as unaffected |
| Phase method | Not required for zygosity | Required before cis or trans |
| Assay scope for the relevant variant class | Required | Required. An unseen second allele may sit in a class the assay does not detect |

Zygosity is taken from document 90. A no-call is not reference. A parent who was not sequenced is not reference.

## Single-sample statements

These are the only inheritance statements available from a proband alone.

| Observation | Statement that may be stored | Statement that is forbidden |
|---|---|---|
| Heterozygous | Compatible with a dominant pattern that acts in the heterozygous state. Not enough for a recessive diagnosis | De novo. Inherited. Phase with any other heterozygous site |
| Homozygous alternate | Compatible with a recessive pattern at this site. Also compatible with a dominant allele in the homozygous state, which can be a different phenotype | That homozygosity proves consanguinity or identity by descent |
| Two heterozygous alleles at one site (`1/2`) | Two different alternate alleles are present. Phase between other sites is still unknown | Compound heterozygosity with a second site |
| Hemizygous alternate on X, karyotype XY, outside the pseudoautosomal intervals | Compatible with an X-linked pattern in that karyotype | A female carrier state. A pseudoautosomal interpretation without an interval list |
| Heterozygous on X, karyotype XX | Compatible with heterozygous X-linked carriage or with X-linked disease, depending on the disease record. The record must say which | A male-specific conclusion |
| Mitochondrial allele with a valid heteroplasmy fraction | The fraction is reported. Compatibility with a mitochondrial disease is `not_assessed` unless a laboratory rule exists | A diploid GT converted into a fraction. A claim that the variant is homoplasmic or heteroplasmic without the fraction and the limit of detection |
| No variant in a recessive gene | Nothing about inheritance | That the gene is excluded. Document 91’s negative-result rule still applies |

A single heterozygous variant in a recessive gene is `recessive_incomplete`. It is not incompatible with recessive inheritance, because a second allele may be unseen, unphased, or of a class the assay does not detect. It is not a positive recessive result either.

## Family statements

When both parents are present as identified samples, the module may compute Mendelian consistency for the nuclear variants it can see.

| Pattern | Automatic statement | Still required before a stronger claim |
|---|---|---|
| Proband heterozygous, both parents high-quality reference at the normalized allele | Apparent de novo | Confirmation that the parents are the biological parents, that coverage in both parents could have seen the allele, and that the allele is not an artifact. ACMG/AMP distinguishes confirmed de novo from assumed de novo. This module does not assign either criterion code |
| Proband heterozygous, one parent carries the allele, the other is high-quality reference | Transmitted from the carrying parent | Parentage, and a check that the other parent’s depth was adequate. Transmission is not pathogenicity |
| A parent is affected and carries the allele | Compatible with transmission | The parent’s phenotype must have been supplied. The module does not assume a parent is affected or unaffected |
| An unaffected parent carries a dominant allele | Not automatically incompatible | Penetrance, age, and whether the parent was examined. Unknown penetrance means the observation is recorded and the pattern is not failed |
| Proband homozygous and only one parent is a carrier, the other parent high-quality reference | Mendelian inconsistency under the assumption of correct parentage and no deletion | A deletion or a dropout can mimic this. The result is a QC flag, not a non-maternity or non-paternity call |
| Parent genotype no-call or below the parent depth rule | Transmission `not_assessable` | Do not fill the parent with reference |

One parent only. Transmission can be assessed for that parent. De novo cannot be assessed. The untested parent is `parent_not_tested`.

No parents. All of the family rows are `not_assessable`. The single-sample table still applies.

## Modes

### Autosomal dominant

Heterozygous is compatible. Homozygous is not excluded and may be phenotypically different. The module does not predict severity. An unaffected carrier parent is a penetrance question, not an automatic exclusion. A new heterozygous allele is not de novo without both parents.

### Autosomal recessive

Homozygous alternate is compatible at that site and is still not a diagnosis. Two heterozygous sites in the same gene are a possible compound-heterozygous pair only. Without phase or informative parental genotypes, the state is `phase_unknown`. Parental genotypes support trans when one variant is transmitted from each parent and both parents’ calls pass quality. Read-backed phase supports cis or trans only for the bases the reads actually span, and only when the phase method is stored. Statistical phasing from a population panel does not support trans.

A heterozygous parent of a homozygous proband is the expected carrier pattern. It is not a statement that the parent is affected.

### X-linked

The laboratory karyotype gates the logic. This module does not determine sex. Discordance between karyotype and sex-chromosome ploidy stops the X-linked conclusion and raises the QC flag from document 89.

For a karyotype XY, a hemizygous alternate outside the pseudoautosomal region is the relevant observation. For a karyotype XX, heterozygous and homozygous observations are distinguished and then interpreted only as far as the disease record allows. Some X-linked diseases are expressed in heterozygous XX individuals and some are not. If the record does not say, the module stops at zygosity.

Transmission from a father to an XX child, and lack of father-to-son transmission for a non-pseudoautosomal X variant, can be tested when those relatives are sequenced and the intervals are known. They are not tested by assumption.

### Mitochondrial

Maternal transmission can be suggested when the mother carries a mitochondrial allele and the father does not, and the mitochondrial representation rules in document 90 are met. Heteroplasmy level can differ between relatives. A failure of the father to carry the allele is expected and is not evidence against the call. Apparent paternal transmission of a mitochondrial allele is a QC flag, because nuclear inserts and sample issues can mimic it. The module does not decide which explanation is true.

A mitochondrial disease label in a gene record does not make a nuclear variant mitochondrial.

### De novo

Allowed phrase when both parents have adequate reference calls: “apparent de novo; parentage not confirmed by this module.”

Forbidden phrases: “de novo mutation,” “PS2,” “PM6,” and any sentence that the allele explains the phenotype because it is new. Mosaicism in a parent can look like absence if the parent’s allele fraction is below the parent assay’s limit. That limitation is printed with every apparent de novo.

### Compound heterozygosity

Allowed phrase without phase: “two heterozygous variants in the same gene; phase unknown; not established as compound heterozygous.”

Allowed phrase with one variant inherited from each parent, both calls passing: “parental transmission is consistent with trans.”

Allowed phrase with read-backed phase and a stored method: “read-backed phase supports cis” or “supports trans,” naming the method and the distance spanned.

Forbidden: collapsing those three phrases into one.

### Homozygosity

A homozygous call is an observation about one site. Runs of homozygosity are a different analysis. This specification does not include a consanguinity detector. A future one would need its own validation. Until then, consanguinity is taken only from the pedigree metadata, and an unstated pedigree is `consanguinity_not_stated`, not denied and not assumed.

Shared identity by descent is not inferred from one homozygous rare allele.

### Penetrance and variable expressivity

If an affected person lacks the family variant, or an unaffected person carries a dominant variant, the module records the observation under the affected-status values that were supplied. It does not compute a penetrance percentage. It does not change the variant’s class. Age and “not assessed” status are displayed. A family of one cannot support a segregation claim.

### Mosaicism

An allele fraction is not a mosaic call. Document 91 gives the assay limits. A parent whose blood does not show a child’s heterozygous variant may still be mosaic. The module may say that parental mosaicism was not tested. It may not say the variant is new in the child in a way that excludes parental mosaicism, except by repeating that the test did not exclude it.

Post-zygotic mosaicism in the proband is a laboratory interpretation of allele fraction, tissue, and confirmation. The software displays the fraction when AD or an equivalent field exists.

## What cannot be concluded without parents or phase

| Conclusion | Required evidence | If absent |
|---|---|---|
| De novo | Both parents, adequate depth, allele absent in both, parentage addressed | `not_assessable` |
| Inherited from a named parent | That parent’s genotype | `not_assessable` |
| In trans | Parents showing transmission of one allele each, or a phase method that spans the sites | `phase_unknown` |
| In cis | The same | `phase_unknown` |
| Parent of origin | Informative parental genotypes or a valid phase method | `not_assessable` |
| Non-penetrance | A reliable unaffected status, an age or examination note, and the genotype | `not_assessable` |
| Segregation across a pedigree | Genotypes and phenotypes for those relatives | `not_assessable` |
| Exclusion of a recessive gene | Both alleles assayed, including the variant classes the disease uses, at validated coverage | `not_covered` or `not_in_validated_class` |
| Exclusion of a dominant de novo mechanism | Both parents tested | `parent_not_tested` |

## Single-sample workflow compared with a trio

| Question | Proband only | Trio with passing parental calls |
|---|---|---|
| Zygosity | Yes | Yes |
| Compatibility with dominant heterozygosity | Yes, as compatibility only | Yes, plus transmission if a parent carries it |
| Recessive homozygote | Compatibility at that site | Compatibility plus carrier parents if observed |
| Second recessive allele | Not established | Trans only if the parents split the two alleles |
| De novo | No | Apparent only |
| Phase of two distant hets | No | Yes if transmission splits them. Read-backed phase can also do this in a single sample when the reads span both sites. Distance matters and must be stored |
| Reduced penetrance | No | Only as an observation, and only with phenotypes |
| Mitochondrial maternal transmission | No | Suggestive if maternal and paternal genotypes exist |
| Diagnosis | No | No |

A trio does not repair assay limitations. Parents sequenced on an assay that does not detect the variant class cannot clear a de novo or a transmission question for that class.

## Automatic checks and human checks

Automatic. Zygosity. Comparison with the curated mode. Mendelian arithmetic on samples that exist. Emission of `not_assessable` with the missing input named. A QC flag when the arithmetic is inconsistent.

Human. Every apparent de novo. Every possible compound-heterozygous pair. Every unaffected carrier. Every Mendelian inconsistency. Parentage. The decision that a pattern is clinically relevant.

The automatic check writes the flag. The person writes the interpretation.

## Failure conditions

| Failure | Result |
|---|---|
| Inheritance label missing | Zygosity only |
| Karyotype missing on X or Y | Sex-linked conclusion blocked |
| Pseudoautosomal intervals not pinned | Calls in those intervals are `ambiguous_variant` for sex-linked logic |
| Parental GT below quality | That parent is not used. Do not average two parents of unequal quality |
| Pedigree disagrees with the sample columns | Family analysis blocked. Single-sample analysis may continue |
| Two inheritance modes curated for one gene | Two compatibility statements. They are not merged into the more convenient one |

## Sources

- Document 90 for genotype and phase representation.
- Document 91 for unseen variant classes, mosaicism, and mitochondria.
- Document 62 for the existing `phase_unknown` and copy-number states.
- Richards and colleagues, 2015, PMC4544753, for the distinction, used here only as a warning, between a confirmed de novo observation and an assumed one. Criterion codes are not assigned.
- Rehder and colleagues, 2021, for parental and mosaic coverage limits and for the statement that short-read phasing is a reason long reads are superior. This module does not claim read-backed phase beyond the bases a stated method spans.

No segregation probability and no LOD score are defined.
