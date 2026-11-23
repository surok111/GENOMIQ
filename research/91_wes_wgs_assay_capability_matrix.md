# 91. WES and WGS assay capability matrix

Accessed 23 November 2026. This matrix states what a geneticist may and may not assume from an ordinary short-read exome VCF or an ordinary short-read genome VCF. It is a limitation statement. It is not a validation of any kit, caller, or laboratory.

The labels WES and WGS are method families. Document 62 already says they are not evidence that a variant class was validated. The same rule is applied here to diagnostic variant classes. A genome file does not automatically repair an exome limitation. A region that is hard for short reads remains hard when the library is a genome.

Where this document says “potentially detectable,” it means the method can produce evidence of that class in favorable regions when the laboratory has validated the class. It does not mean the class was detected in a particular file.

## Sources for the comparison

Retrieved and used:

- Rehder and colleagues, Genetics in Medicine, 29 April 2021, ACMG technical standard for constitutional NGS. Exome sequencing targets coding sequence plus adjacent intronic bases and has uneven coverage. Genome sequencing does not use hybridization enrichment, has more even coverage across the exome, examines over 90 percent of the genome, can produce mitochondrial sequence, and has increased capacity for SNVs, CNVs, rearrangements, and repeat expansions. That capacity still requires specialized pipelines. Short reads are limited in homologous and low-complexity regions. The standard names CYP2D6, GBA, PMS2, STRC, and the HLA genes as examples where long reads are more capable. Long-read analysis is outside this module. The standard also says complete coverage is not expected for exome or genome tests.
- The same standard’s intronic-content note: in a ClinVar extract, coverage through acceptor −16 and donor +5 would include more than 97 percent of pathogenic or likely pathogenic intronic variants then in that extract, with an acknowledged bias toward variants people already report and already sequence. That figure is not a sensitivity for deep intronic or regulatory variants.
- Raca and colleagues, Genetics in Medicine, published 12 December 2022, ACMG points to consider for germline structural variants from NGS. Copy-number sensitivity, specificity, and resolution are assay-dependent. Exome and other capture methods are less reliable than PCR-free genome sequencing. Exon-level events remain challenging. Homologous and GC-rich regions may not support a call. A single resolution for a whole exome or genome is often not honest. Low-pass genome sequencing is described for larger CNVs and is not reliable for SNVs or for CNVs at or below about 25 kb. The figure is theirs, for that application, and is not a threshold for this module.
- Documents 34, 42, 43, and 62 of this series, for the local conclusion that CYP2D6 structure and HLA type are assay claims, not genome-wide sequencing claims. Those documents are pharmacogenetic. They are cited here only for the assay-boundary point.

Not retrieved, and therefore not used as numbers: a kit-by-kit comparison of capture BEDs, a GIAB difficult-region benchmark, the NCBI difficult-region compilation cited by ACMG as NBK535152, and any measurement of analytic sensitivity for a named caller. Those omissions are gaps in this matrix. They are not evidence that a class is easy or impossible.

## Status words

| Status | Meaning |
|---|---|
| Potentially detectable | A validated short-read assay of this method can often call the class in ordinary unique sequence. The file still has to show a call that passes the laboratory’s rules |
| Detectable with additional validated methods | The ordinary SNV/indel VCF is not enough. A named additional caller, library protocol, or orthogonal assay must be in the test scope |
| Not reliably detectable from ordinary short-read data | Short-read alignment itself is a poor observer of this class. Labeling the test WGS does not move the class into the first row |
| Requires separate confirmation | Even a high-quality candidate in this class is incomplete until the laboratory’s confirmatory policy is satisfied. If no policy is stated, confirmation status is `not_stated` |

A class can carry more than one status. An exonic SNV is potentially detectable and still requires whatever confirmation policy the laboratory declared. If the policy is absent, the candidate is not “confirmed” and is not “failed.”

## Shared limits

These apply to both methods.

- Short reads mis-map in segmental duplications, pseudogenes, and other homologous sequence. The result can be a false variant or a missed variant. ACMG 2021 states this limitation directly.
- GC-rich sequence and low-complexity sequence reduce coverage or mapping quality on both methods. Capture makes the coverage loss less uniform. It is not the only cause.
- A variants-only VCF cannot show that a region was covered. A negative gene statement needs the assay’s interrogated intervals and a coverage summary, or a gVCF profile the laboratory has defined.
- Complete coverage of every clinically relevant base is not an expected property of either method.
- Analytical sensitivity for one variant class is not transferable to another.
- Orthogonal confirmation of SNVs is a laboratory policy. ACMG 2021 says that, without a validated policy based on that laboratory’s metrics, confirmation remains the practice. This module records the policy. It does not waive it.

## Method differences that are supported by the 2021 standard

| Property | Exome | Genome |
|---|---|---|
| Enrichment | Hybridization or amplification of selected targets. Targets are kit-specific and were not inventoried here | No hybridization enrichment in the standard PCR-free or shotgun design |
| Coverage shape | Uneven. Analytical sensitivity can be lower than a disease panel that was optimized for the same genes | More even across exons. Mean depth is often lower than an exome or a panel. Evenness does not equal completeness |
| Intronic and intergenic sequence | Only what the kit and the analysis interval include, often a short flank | Sequenced in large part. Over 90 percent is the standard’s figure, not 100 percent |
| Noncoding disease variants | Missed when outside the capture and the analysis interval | Potentially present in the reads and still invisible in the report if the analysis was restricted to exons |
| Mitochondrial genome | Not guaranteed. Off-target reads are not a validation | Produced by genome sequencing and interpretable only if the laboratory analyzed that contig and set a heteroplasmy limit |
| CNV and rearrangement capacity | Possible with a dedicated caller. Capture density, GC, and homology limit it | Greater capacity, especially PCR-free, and still caller-dependent and region-dependent |
| Repeat expansions | Not an expected output of an exome SNV/indel call | Increased capacity only with a specialized pipeline. An ordinary VCF is not that pipeline |
| Time and uniformity advantages claimed for genomes | Not claimed | The 2021 standard says genome data can be produced more rapidly and with more even exome coverage. Those are method properties, not diagnostic completeness |

## Variant-class matrix

### Single-nucleotide variants and small indels in unique coding sequence

| | Exome | Genome |
|---|---|---|
| Status | Potentially detectable | Potentially detectable |
| Condition | The base is inside the validated capture and above the laboratory’s depth and quality rules | The base is outside a difficult region and above the laboratory’s rules |
| Confirmation | Laboratory policy. Unstated policy means `not_stated` | Same |
| What must not be said | That every exon in the gene was covered, or that a missing variant record means the gene was reference | That lower average depth still covers every medically relevant base, or that a clear coding SNV result covers noncoding mechanisms |

Small indels are more error-prone than SNVs near repeats and at homopolymers. A left-aligned indel in unique sequence is in the potentially detectable class. The same indel in a homopolymer is a quality-review case, not an automatic pass.

### Exome capture boundaries and poorly captured exons

| | Exome | Genome |
|---|---|---|
| Status | Not reliably detectable for bases the kit does not target or consistently fails | Potentially detectable for those coding bases, if the laboratory’s genome validation includes them |
| Why | Capture design, bait failure, GC content, and homology. Different kits target different exon sets. This pass did not diff any BED files | Genome sequencing does not depend on those baits. It still depends on mapping and on depth |
| Required metadata | The analysis BED and a per-sample coverage summary before any negative statement | The difficult-region mask the laboratory uses, plus coverage |
| Forbidden inference | A gene-level negative from a VCF that happens to contain no alternate allele | A gene-level negative in a region the laboratory still marks as difficult |

### GC-rich sequence

| | Exome | Genome |
|---|---|---|
| Status | Often poorly covered. Treat as not reliably detectable where the sample’s coverage fails the laboratory rule | More even, and still able to fail. PCR-containing genome libraries reintroduce GC bias. PCR-free is a protocol claim, not a synonym of WGS |
| Required metadata | Whether the library is PCR-free, and the coverage at the site | Same |
| Forbidden inference | That a low-coverage GC exon was reference | That “WGS” means the library was PCR-free |

### Canonical splice sites and nearby splice-region bases

Canonical donor and acceptor dinucleotides are potentially detectable on an exome when the capture flank includes them, and potentially detectable on a genome in unique sequence. ACMG 2021 suggests designing targets so that acceptor −1 through −16 and donor +1 through +5 are available, because of the ClinVar extract described above.

| | Exome | Genome |
|---|---|---|
| Status | Potentially detectable only inside the flank the kit actually captures | Potentially detectable in unique sequence |
| Additional method | A splice prediction is not detection. It is an annotation. Functional RNA evidence is a separate assay | Same |
| Forbidden inference | That a splice consequence term is pathogenic | That a genome result saw every deep intronic splice variant in the disease |

### Deep intronic and regulatory variants

| | Exome | Genome |
|---|---|---|
| Status | Not reliably detectable. Usually outside the capture. A kit that spikes in known pathogenic intronic sites covers those sites only | The bases may be sequenced. Detection still requires the analysis to examine them and the mapping to be reliable. Regulatory consequence is not established by observing the base |
| Additional method | A targeted assay for a known deep intronic allele | Functional or RNA studies for effect. Those studies are out of scope for this VCF module |
| Forbidden inference | Absence of an intronic call from an exome is not a negative intronic test | A genome VCF restricted to exonic analysis is not a regulatory-variant test |

### Copy-number variants

| | Exome | Genome |
|---|---|---|
| Status | Detectable with additional validated methods. Not reliably detectable from read depth alone in GC-rich or homologous sequence. Exon-level events are the hardest | Potentially detectable when a validated CNV caller was run, with resolution stated by size or by exon count, and with lower reliability in homologous and GC-rich sequence |
| Ordinary SNV VCF | Not a CNV test on either method | Not a CNV test |
| Confirmation | The laboratory’s SV policy. Unstated means `not_stated`. Breakpoint precision must be labeled | Same. Raca and colleagues say one resolution figure for the whole assay is often not accurate |
| Forbidden inference | That a normal exome SNV result excludes a deletion | That a genome result excludes an exon-level deletion in a homologous gene, or that every CNV caller agrees |

### Structural variants other than copy number

Inversions, insertions, translocations, and complex rearrangements.

| | Exome | Genome |
|---|---|---|
| Status | Generally not reliably detectable. Capture does not observe most breakpoint junctions | Detectable with additional validated methods. The 2021 standard attributes increased capacity to genome sequencing and still requires a specialized pipeline. Balanced events and insertions in repeats remain difficult on short reads |
| Ordinary VCF | No SV records means the class was not in the file. It does not mean the class was reference | Same |
| Confirmation | Orthogonal methods such as karyotype, FISH, or long-read sequencing are laboratory choices. This module does not select one | Same |
| Forbidden inference | A negative exome excludes a structural diagnosis | A short-read genome excludes a structural diagnosis |

### Repeat expansions

| | Exome | Genome |
|---|---|---|
| Status | Not reliably detectable from ordinary short-read data | Not reliably detectable from an ordinary SNV/indel VCF. Detectable only with an additional validated method. Short-read expansion callers exist and were not evaluated here. Long-read sequencing is the method ACMG 2021 identifies as superior for expansions such as fragile X |
| Forbidden inference | A normal exome addresses the expansion | A normal short-read genome addresses the expansion |

### Mitochondrial variants and heteroplasmy

| | Exome | Genome |
|---|---|---|
| Status | Not assumed. Detectable only when the laboratory validated mitochondrial analysis on that exome | Potentially detectable for higher heteroplasmy levels when the mitochondrial contig was analyzed and the limit of detection is stated. Low heteroplasmy is a depth-and-validation question. ACMG 2021 notes that detection near 5 percent needs substantially higher coverage than a constitutional nuclear heterozygous call |
| NUMT | Requires separate review on both methods. The VCF cannot by itself prove a call is mitochondrial rather than a nuclear insert | Same |
| Representation | A diploid genotype is the wrong object. Document 90 rejects it as a heteroplasmy result | Same |
| Forbidden inference | Off-target mitochondrial reads are a clinical mitochondrial test | A genome that included MT automatically calls low-level heteroplasmy or excludes mitochondrial disease |

### Mosaicism

| | Exome | Genome |
|---|---|---|
| Status | Potentially detectable above the laboratory’s allele-fraction limit in well-covered unique sequence. Deeper exome coverage can help this class and does not validate it | Potentially detectable above the laboratory’s limit. Typical genome depth is lower, so the same fraction can be harder to see. The 2021 standard’s 30–50× illustration for 10–15 percent mosaicism is an illustration, not a local cutoff |
| Additional method | Confirmation policy for low allele fraction. ACMG notes that a negative Sanger result does not by itself prove the NGS call was false | Same |
| Forbidden inference | Allelic imbalance is mosaicism | A heterozygous genome call excludes mosaicism in a parent or in tissue that was not tested |

### Pseudogenes and homologous regions

| | Exome | Genome |
|---|---|---|
| Status | Not reliably detectable from ordinary short-read data when the clinical gene and the pseudogene cannot be distinguished by the reads | The same. Extra genomic coverage does not make short reads unique |
| Additional method | Gene-specific long-range methods, long reads, or another assay the laboratory validated for that gene | Same |
| Examples named by ACMG 2021 | CYP2D6, GBA, PMS2, STRC, HLA | Same examples. The list is not complete. This pass did not open the NCBI homology compilation |
| Forbidden inference | A clean exome genotype in these genes is a resolved genotype | A clean genome genotype in these genes is a resolved genotype |

Document 62 already maps CYP2D6 hybrids, CYP2D6 copy number, and HLA alleles to specific failure states when the assay did not claim them. This matrix does not weaken those states. A diagnostic module must not report those loci as excluded on the basis of a standard short-read VCF.

### HLA

| | Exome | Genome |
|---|---|---|
| Status | Not reliably detectable as an HLA type from ordinary short-read data | Not reliably detectable as an HLA type from ordinary short-read data |
| Why | Extreme polymorphism and homology. Alternate reference contigs are not a typing result. Document 90 leaves those contigs uninterpreted without a named method | Same |
| Additional method | A validated HLA assay | Same |
| Forbidden inference | That an exome or a genome replaced HLA typing | That a variant called on an HLA gene in a standard VCF is the star allele |

### CYP2D6 structural complexity

| | Exome | Genome |
|---|---|---|
| Status | Not reliably detectable for hybrids, deletions, and duplications from ordinary short-read data | Not reliably detectable for those structural alleles from ordinary short-read data. ACMG 2021 names CYP2D6 among loci where long reads are superior |
| SNVs in the gene | Even single-nucleotide calls are unsafe when reads may belong to CYP2D7 or CYP2D8. Treat the locus as homologous unless the assay says otherwise | Same |
| Additional method | A validated CYP2D6-specific method, including copy number, as already required for the pharmacogenetic rules | Same |
| Forbidden inference | A WGS label satisfies the CYP2D6 structural rules in documents 34, 42, and 62 | A missing *5 or a missing duplication in the VCF means copy number is two |

### Other difficult regions

The 2021 standard also identifies low-complexity sequence, repetitive sequence, and hypervariable sequence as accuracy problems, and methylation as a mechanism NGS does not observe.

| Class | Both methods |
|---|---|
| Homopolymers and short tandem repeats below the scale of a named expansion disorder | Calls are review items. Not a blanket failure and not a blanket pass |
| Mobile-element insertions | Detectable with additional validated methods on genomes. Not an expected exome result. Not evaluated caller by caller here |
| Methylation and imprinting abnormalities | Not detectable from a sequence VCF. Requires a separate method |
| Balanced rearrangements below the SV caller’s validated resolution | Not reliably detectable |
| Variants only on an ALT contig | Not interpreted, per document 90 |

## How the workflow uses this matrix

Stage 5 and stage 11 read the assay’s `test_scope`. If the scope does not list the class, every record of that class is `not_in_validated_class`. The candidate list does not drop the limitation. The report states the class as not assessed.

If the scope lists the class, records still pass through the laboratory’s quality rules and the difficult-region flag. A pass is “called under this assay’s rules,” not “the locus is straightforward in the literature.”

A negative statement about a gene is allowed only when three things are present: the gene’s relevant intervals are in the validated set, the sample’s coverage meets the laboratory’s threshold on those intervals, and the variant classes that cause that disease are in the validated set. If any of the three is missing, the gene is `not_covered` or `not_in_validated_class`. It is not negative.

## What would change the matrix later

A laboratory validation summary could move a cell for that laboratory only. For example, a genome assay with a validated CYP2D6 reflex could change the CYP2D6 cell for that `assay_id`. The change is metadata. It is not a reason to edit the default cell for everyone else.

A benchmark that was not read in this pass could refine the difficult-region list. Until it is read, the list stays the ACMG examples plus the homologous-locus rule.

## What this matrix must not be used to say

That an exome is inappropriate. That a genome is comprehensive. That short-read SNVs in unique exons are unreliable. That any named gene outside the ACMG examples is easy. That the patient does not have a class of variant the assay did not assess.
