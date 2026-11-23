# 98. Existing tools and standards review

Accessed 23 November 2026. This document records standards and tools that a future WES/WGS review module would have to live beside. It is a selection aid. It is not a bill of materials. Most of these should remain references. A few are plausible optional integrations after a version is pinned and a license is checked. None is adopted by this research pass.

“Reference” means the module must be able to cite it and must not contradict its constraints. “Dependency” means a future implementation cannot perform a named function without a pinned version of it. “Optional integration” means the function can ship without it. A dependency in this table is a future dependency, not a library already added to GenomIQ.

Licenses change. Where the license file was not opened on 23 November 2026, the table says so. Those rows must be rechecked before any distribution.

## Specification and representation

| Item | Problem it solves | Input | Output | Role here | License and operation |
|---|---|---|---|---|---|
| VCF 4.2 through 4.5, samtools hts-specs. VCFv4.5 dated 25 February 2026 was read | A common file for variants and genotypes | Caller records | The eight fixed fields plus optional sample fields | Dependency for the future parser. Document 90 is the clinical contract on top of it | The specification is public. htslib and bcftools are the usual open-source readers. Pin the version. This pass did not vendor them |
| GA4GH Variation Representation Specification (VRS) | A computable allele identity so string forms can be compared | Alleles | Identifiers and normalized allele objects. gnomAD v4.0 states that it includes VRS annotations | Optional. Useful later for identity. Not required to accept a VCF | Specification is public. A library would be an implementation choice. Not selected here |
| GA4GH Phenopackets | An exchange format for phenotype, pedigree, and variant interpretation | Clinical and family description | A structured packet. The variation-descriptor page distinguishes descriptors and points at VRS and GENO zygosity | Optional, after a version is reviewed. The full schema was not read | Schema is public. Not an internal clinical record until reviewed |
| HGVS nomenclature | Human-readable allele names | A transcript version and an allele | Coding and protein expressions | Reference. HGVS is displayed only when a pinned annotator emits it with a transcript version | The nomenclature site was not re-read. Pin the nomenclature version the annotator claims |
| MANE Select | A default matched RefSeq and Ensembl transcript | Gene | A transcript version | Reference for the transcript policy when the laboratory adopts it. The MANE release was not downloaded | Public transcript set. Pin the release. Do not treat it as the transcript used in the patient’s tissue |
| Sequence Ontology consequence terms | A controlled vocabulary for molecular consequence | Annotator decision | Terms such as missense or splice donor | Reference vocabulary for document 92. The ontology file was not downloaded | Public. Pin the term version the annotator emits |

VRS does not interpret pathogenicity. Phenopackets do not interpret pathogenicity. Using either format would not satisfy the clinical rules in documents 92 through 97.

## Phenotype and gene-disease knowledge

| Item | Problem it solves | Input | Output | Role here | License and operation |
|---|---|---|---|---|---|
| Human Phenotype Ontology | Controlled phenotype terms and parent-child structure | Clinical findings coded by a person | Term identifiers and a graph | Dependency if, and only if, phenotype ranking is turned on. Without a pin, ranking stays off | Ontology is public. Release was not downloaded. Obsolete-term replacement must come from that release |
| HPO disease annotations (`phenotype.hpoa` or a successor the pin names) | Links diseases to terms, sometimes with frequency | A disease identifier | A term set | Dependency for any comparison in document 93 | Not downloaded. Annotations are not diagnostic criteria unless a separate pin says so |
| ClinGen gene-disease validity, Strande, Riggs, and colleagues, American Journal of Human Genetics, 2017, and later SOP | Separates established gene-disease pairs from limited, conflicting, disputed, and refuted ones | Curated evidence | A validity class per gene-disease pair | Reference, and a future dependency for the validity dimension. The 2017 classes were read. The current SOP was not | Public curations. Many genes are uncurated. Uncurated is a state, not a negative |
| ClinGen Variant Curation Expert Panel specifications | Disease-specific use of ACMG/AMP criteria | A gene and a variant | Criteria and thresholds for that gene | Reference for human reviewers. Not an automatic engine | Public when released. Do not apply one gene’s thresholds to another gene |
| ACMG Secondary Findings list. v3.3 identified, Genetics in Medicine, 23 June 2025, PMC12318660 | A minimum list for opportunistic findings in clinical exome and genome tests | An opted-in order | Gene-disease pairs for a separate incidental section | Optional policy, and only the version a laboratory adopts. The gene table was not copied | The statement says this is not indication-based diagnosis and not population screening |

## Variant interpretation framework

| Item | Problem it solves | Input | Output | Role here | License and operation |
|---|---|---|---|---|---|
| Richards and colleagues, ACMG/AMP 2015, PMC4544753 | A shared five-class framework and evidence categories | Laboratory evidence | Pathogenic, likely pathogenic, uncertain, likely benign, or benign, when a person applies the rules | Reference for reviewers. Not a dependency of the automatic path. This module does not assign the classes | The paper is public. The framework is a professional recommendation, not a software license |
| Harrison, Biesecker, and Rehm, 2019, PMC6885382 | A map of ClinGen’s changes to the 2015 criteria, including frequency | Population counts and disease parameters | Warnings and disease-specific threshold examples | Reference. Supports document 92’s refusal to invert BS1 into PM2 | Public |
| ClinGen SVI recommendation to discontinue PP5 and BP6, PMC6709533 | Stops a reputable label from being counted as if it were the underlying evidence | An external classification | A recommendation not to use those two criteria | Reference. Already applied as a prohibition in document 92 | Public |
| Later SVI recommendations on PVS1 weight, PM2 weight, de novo evidence, splicing, and computational scores | Tighten individual criteria | Criterion-specific data | A revised strength | Reference only. The recommendation texts other than the items above were not opened in this pass. They must be pinned before anyone encodes them | Public. Encoding them is a classification engine, which this task does not authorize |
| ACMG/ClinGen constitutional CNV interpretation standard, the journal page opened for this pass | Interpretation and reporting of copy-number variants after they are detected | A resolved CNV | A classification framework for people | Reference when the assay has actually produced a CNV. It does not validate CNV calling | The page states that analytical validation is addressed elsewhere |

The 2015 framework expects the laboratory to see the evidence. A future module that emitted criterion codes without storing the evidence would be out of scope even if it cited this table.

## Population frequency

| Item | Problem it solves | Input | Output | Role here | License and operation |
|---|---|---|---|---|---|
| gnomAD v4.1 on GRCh38. v4.0 announcement read; v4.1 announcement identified | Large reference frequencies, including filtering allele frequency, ancestry-group counts, homozygous counts, and joint allele numbers | A normalized GRCh38 allele | Counts and flags. v4.1 adds a discordant exome-versus-genome flag | Reference, and the default frequency dependency if the laboratory does not pin another resource. v4.0 is GRCh38 only | gnomAD terms were not re-read. Pin the release. Do not combine v2 and v4 on mixed assemblies |
| gnomAD v2.1.1 | A GRCh37-era frequency set | GRCh37 alleles | Counts | Optional and only for GRCh37 files. Not retrieved in this pass | Do not apply to GRCh38 |
| Whiffin and colleagues, Genetics in Medicine, 18 May 2017 | A disease-specific maximum credible frequency | Prevalence, heterogeneity, penetrance, inheritance, and a reference count | A comparison, not a class | Reference method. Optional calculator only after the parameters and the formula, including the inheritance adjustment, are implemented from the paper rather than from memory | The paper’s examples are not local thresholds. Their online calculator was not used |

gnomAD is not a benign database and not a control set cleaned of all disease. Document 92 states the limits that were actually retrieved.

## Annotation tools

| Item | Problem it solves | Input | Output | Role here | License and operation |
|---|---|---|---|---|---|
| Ensembl VEP | Transcript consequence, HGVS, and optional plugins | A normalized VCF and a cache | Consequence records per transcript | Optional integration. A plausible default annotator if the license and cache are pinned. The license file was not opened in this pass | Confirm the license before distribution. Pin the cache and the VEP version. A CSQ field without that pin is unverified |
| ANNOVAR | Another widely used annotator | A VCF or a coordinate list and local databases | Consequence and database hits | Optional and not preferred by this specification. Two annotators are not better until their disagreement is displayed | Academic and commercial terms differ. The license page was not opened on 23 November 2026. Do not add it until that page is read |
| SpliceAI, Jaganathan and colleagues, 2019, as described on the Illumina repository | A prediction of splice gain or loss | Sequence context | Prediction scores | Optional prediction only. Not a consequence group and not a clinical class | The repository states that source code is PolyForm Strict 1.0.0 and that models and precomputed scores are CC BY-NC 4.0 for academic and non-commercial use, with commercial use requiring an Illumina license. That is a distribution constraint, not a scientific endorsement |
| LOFTEE, REVEL, CADD, Pangolin | Loss-of-function filtering or pathogenicity prediction | Alleles | Scores or flags | Optional annotations. gnomAD v4.0 already attaches some of these inside its own browser. A score inside gnomAD is still a prediction | Not opened license by license. Do not let a score set PP3 or BP4. The ClinGen computational-evidence calibration was not opened |
| bcftools norm or an equivalent left-aligner | One indel representation | A VCF and a FASTA | A normalized VCF | A future dependency of document 90’s comparison key. The tool was not selected or run | Pin the tool and the FASTA. Keep the original alleles |

Adding VEP does not add clinical judgement. Adding SpliceAI does not establish a splice defect. The module can ship with a pinned annotator and with prediction turned off.

## Phenotype-ranking tools

| Item | Problem it solves | Input | Output | Role here | License and operation |
|---|---|---|---|---|---|
| Exomiser | Gene ranking from variants plus HPO, using semantic similarity | VCF, HPO identifiers, optional pedigree and Phenopacket. The 14.0.1 documentation says detailed HPO terms strongly influence the result | A ranked gene list and similarity components | Optional external ranker. Its combined score must not become document 95’s order. Term-level output could be stored beside the local table | License was not opened. Data files are large and versioned. Not required |
| Phenomizer, LIRICAL, and similar similarity tools | Ontology-aware phenotype comparison | HPO terms | A similarity and a differential | Same rule as Exomiser. Not evaluated file by file in this pass | Not selected |
| Amelie and other literature-mining rankers | Retrieve published gene-phenotype links | A phenotype | A ranked literature list | Not recommended. A mined sentence is not a pinned curation | Not evaluated |

The local specification in document 93 is intentionally weaker and more inspectable than these tools. That is a product choice. It is not a claim that the local comparison outperforms them.

## Laboratory guidance

| Item | Problem it solves | Role here |
|---|---|---|
| Rehder and colleagues, ACMG constitutional NGS technical standard, Genetics in Medicine, 29 April 2021 | Validation, coverage, confirmation policy, and the difference between panels, exomes, and genomes | Reference. The main source for documents 91 and 97. It tells laboratories to set their own thresholds. It is not a software configuration |
| Raca and colleagues, ACMG germline structural-variant points to consider, Genetics in Medicine, 12 December 2022 | What to demand of an NGS structural-variant assay | Reference for CNV and SV limits |
| CAP molecular checklist and ISO 15189 | Laboratory quality systems | Not opened in this pass. They govern the laboratory, not the layout of a candidate row. A software specification should not pretend to satisfy them |
| New York State germline NGS validation guidance | One regulatory example of confirmation practice, cited inside the ACMG 2021 standard | Not opened. The ACMG standard’s caution, including that a previously confirmed site can still be false in a later sample, is the point used here |

## What should not be added

- A language model that writes the interpretation or maps free text to HPO.
- An automatic ACMG/AMP scorer.
- Every prediction score that a VEP plugin can emit.
- A second frequency database that is not pinned to the same assembly.
- Exomiser’s rank as the GenomIQ rank.
- The ACMG SF gene list as a default filter for every file.
- A liftover step that is not a named, tested procedure with a failed-liftover output.
- PharmVar, CPIC, or a dosing engine inside this diagnostic draft. Those belong to the pharmacogenetic stack. A variant can be relevant to both stacks and still must not produce a dose from this workflow.

## A minimal future set, if the product is ever authorized

This is a recommendation for scoping, not an implementation plan.

1. A VCF reader pinned to an allow-list of versions, and a normalizer pinned to a FASTA.
2. One annotator, pinned, if consequence and HGVS are in scope. VEP is the candidate to evaluate first because it is the usual source of the consequence terms document 92 uses. The license still has to be read.
3. One frequency release on the matching assembly. gnomAD v4.1 is the candidate for GRCh38.
4. A pinned HPO release and a pinned disease-annotation file, only if phenotype ranking is on.
5. A pinned ClinVar release and a pinned ClinGen gene-disease release, as quotations and validity labels, not as an automatic class.
6. No prediction tool and no external ranker in the first version.

That set still does not classify variants. It is enough to feed the review surface in document 96.

## Sources opened or identified on 23 November 2026

Opened far enough to use: VCFv4.5 PDF; Rehder 2021; Raca 2022; Richards 2015 PMC page; Harrison, Biesecker, and Rehm 2019; the PP5/BP6 letter; Whiffin 2017; Strande and Riggs 2017; gnomAD v4.0 announcement; ACMG SF v3.3 PMC page; Exomiser 14.0.1 advanced-analysis page; the SpliceAI repository description and license statement; the Phenopackets variation-descriptor page.

Identified and not used as a field-level source: gnomAD v4.1 announcement details beyond the joint allele-number and discordant-frequency changes; ClinVar review-status legend; current ClinGen SOP; MANE release notes; VEP license; ANNOVAR license; Exomiser license; CAP and ISO texts; the GIAB and NCBI difficult-region resources.

Unread licenses and unread SOPs are gaps. They are not permission to proceed without them.
