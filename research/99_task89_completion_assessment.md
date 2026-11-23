# 99. Task 89 completion assessment

Accessed 23 November 2026. Task 89 asked for a research-only functional specification of a deterministic WES/WGS review workflow. The specification is in documents 89 through 98. This note says what was completed, what was left open, and what was not changed.

## Deliverables

| Document | Content | Status |
|---|---|---|
| 89 | Fourteen-stage workflow, with purpose, inputs, outputs, failures, automation, human review, and forbidden inferences | Written |
| 90 | VCF contract: versions, alleles, contigs, normalization, genotypes, depth, filters, phase, structural and mitochondrial representation, sample identity | Written |
| 91 | WES versus WGS capability matrix, including the classes the task named | Written |
| 92 | Technical, frequency, consequence, and clinical-evidence filters, without a universal frequency cutoff | Written |
| 93 | HPO comparison, including missing, excluded, and age-dependent phenotypes | Written |
| 94 | Inheritance and segregation, including the single-sample case | Written |
| 95 | Twelve inspectable dimensions and a lexicographic order, including the hard cases | Written |
| 96 | Candidate review surface | Written |
| 97 | Laboratory draft, result classes, and the empty-list wording | Written |
| 98 | Standards and tools, with most of them kept as references | Written |

No production parser, knowledge-base record, clinical classification, or report generator was written.

## Findings that constrain any later design

1. The workflow can be deterministic and still be diagnostically incomplete. Determinism means the same file, the same metadata, and the same pinned releases produce the same dispositions. It does not mean the genome was fully tested.

2. The VCF specification requires a versioned header and eight fixed columns. Clinical use also requires a declared build, a contig map, a genotype when zygosity is shown, and a refusal to treat a missing filter or a missing site as a normal result. Depth, allelic depth, phase method, and clinical annotations are frequently absent and must stay absent rather than be filled.

3. Exome and genome sequencing are not interchangeable. Genomes cover more noncoding sequence, have more even exome coverage, and have more capacity for copy-number and structural callers. Short-read genomes do not reliably resolve homologous loci, repeat expansions, methylation, or low-level mosaicism, and they do not validate a class the laboratory did not claim. CYP2D6, HLA, GBA, PMS2, and STRC remain difficult on both methods. Those gene names come from the ACMG 2021 standard and, for CYP2D6 and HLA, from earlier documents in this series.

4. Technical failure, high frequency under a stated model, a benign-looking consequence, and an external benign assertion are different events. Common does not mean benign. Rare does not mean pathogenic. A frequency screen runs only when prevalence, heterogeneity, penetrance, inheritance, and the resource are all stored.

5. Phenotype ranking uses HPO identifiers and the ontology graph. It shows matches and conflicts as terms. It does not emit a diagnostic probability. Missing phenotype information turns phenotype ranking off. It does not impute a textbook phenotype and it does not weaken a molecular observation.

6. A single sample supports zygosity and a limited compatibility statement. It does not support de novo, parent of origin, or trans. Two heterozygous variants in a recessive gene stay phase-unknown until parents or a spanning phase method say otherwise. A trio does not repair an unvalidated variant class.

7. Prioritization keeps technical reliability, assay limits, gene-disease validity, external evidence, consequence, frequency, inheritance, phase, phenotype, conflict, and missing data as separate states. The default order is a documented sort. It is not a score. Conflict is shown early. An empty list is inconclusive.

8. The review surface and the draft have to show contrary evidence, missing data, and provenance. The software does not assign an ACMG/AMP class, does not sign, and does not describe an empty draft as a negative genome. Established diagnosis and incidental finding are reviewer decisions under an explicit policy.

9. A minimal later stack, if the product scope is ever authorized, is a versioned VCF reader and normalizer, one annotator, one frequency release on the matching assembly, and pinned HPO, ClinVar, and ClinGen releases. Prediction tools, Exomiser’s rank, and an automatic criterion engine are not part of that minimum.

## Relationship to earlier research

Document 26 says disease interpretation is a separate stack and is not authorized merely by building more pharmacogenetic rules. This task does not authorize that stack. It specifies the stack so a later decision can be made against a concrete workflow.

Document 62’s refusal rules are reused: no guessed build, no negative result without an interrogated interval, no universal depth, no mosaicism inferred from allele fraction, and no CYP2D6 or HLA conclusion without an assay claim. Documents 89 through 97 do not weaken those rules.

The pharmacogenetic report rules in document 17 are not the report in document 97. A diagnostic draft must not emit a dose. A pharmacogenetic result must not be described as a Mendelian diagnosis.

## Sources actually used

Read on 23 November 2026 far enough to support the claims that cite them:

- VCFv4.5, 25 February 2026, samtools hts-specs printing e821e4f.
- Rehder and colleagues, Genetics in Medicine, 29 April 2021.
- Raca and colleagues, Genetics in Medicine, 12 December 2022.
- Richards and colleagues, 2015, PMC4544753.
- Harrison, Biesecker, and Rehm, 2019, PMC6885382.
- ClinGen SVI letter on PP5 and BP6, PMC6709533.
- Whiffin and colleagues, Genetics in Medicine, 18 May 2017.
- Strande, Riggs, and colleagues, American Journal of Human Genetics, 2017.
- gnomAD v4.0 announcement, 1 November 2023.
- ACMG SF v3.3, Genetics in Medicine, 23 June 2025, PMC12318660. The gene table was not copied.
- Exomiser 14.0.1 documentation page on HPO input.
- SpliceAI repository license statement.
- Documents 17, 26, 34, 42, 43, and 62 of this series, for local boundaries.

gnomAD v4.1 was identified for joint allele numbers and the discordant-frequency flag. The full v4.1 note was not the basis for any other claim.

## Remaining research gaps

These gaps were left open on purpose. They are not negative biological findings.

- The current ClinGen SOP that separates disputed and refuted gene-disease evidence was not downloaded. The 2017 class names are the ones cited.
- The ClinVar variant XML or VCF release, and the review-status legend that would be pinned with it, were not downloaded.
- No HPO release or `phenotype.hpoa` file was downloaded, so no information content was computed and no term was matched.
- MANE release notes, the HGVS nomenclature page, and the Sequence Ontology file were not downloaded.
- VEP, ANNOVAR, and Exomiser license files were not opened. SpliceAI’s repository license statement was read. Commercial use of SpliceAI models is restricted.
- CAP checklists and ISO 15189 were not opened.
- No capture-kit BED was compared. Kit-specific exon coverage is therefore stated as a required input, not as a table of kits.
- The NCBI difficult-region compilation cited by ACMG, and current GIAB benchmarks, were not opened. The homologous-gene examples are the ones named in the 2021 standard, not a full difficult-region catalog.
- Later ClinGen criterion recommendations, including the exact current point value for PM2 and the computational-evidence calibration, were not opened. The specification forbids encoding them until they are pinned.
- No caller comparison was run. GATK, DeepVariant, DRAGEN, and others are not claimed to emit the same FORMAT keys.
- Liftover accuracy was not tested. Liftover is not part of the workflow.
- Secondary-findings policy was specified as an opt-in. The v3.3 gene list was not transcribed.
- No synthetic VCF was run through the rules, because no parser was written. The patterns in document 95 are specification checks for a later implementation, not executed tests.
- Document 26’s product decision, whether GenomIQ will interpret Mendelian disease at all, remains unresolved. This task does not resolve it.

## Confirmation

No file under `src/`, `data/`, `reports/`, or the generated knowledge-base JSON was modified. No parser was modified. No clinical classification in the knowledge base was changed. No patient data were read or created. No language-model runtime was added. No automatic diagnostic rule was implemented. The only files created are the eleven research documents named in the task, including this assessment.
