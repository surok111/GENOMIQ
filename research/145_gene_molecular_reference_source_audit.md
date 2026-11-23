# 145. Gene and molecular reference source audit

Accessed 23 November 2026. GenomIQ needs stable identities for genes, transcripts, proteins, assemblies, alleles, and structural variants. A symbol is not an identity. A coordinate without a build is not an identity. An HGVS string without a transcript version is not an identity.

## NCBI Gene, RefSeq, and the molecular-data policy

The NCBI policy page was fetched. For molecular databases, NCBI says it places no restrictions on use or distribution and does not accept data whose submitter requested a reuse restriction. It also says some submitters, or a country of origin, may still claim intellectual-property rights, and that NCBI cannot pass on a right it does not have.

That policy covers Gene, RefSeq nucleotide and protein records, and dbSNP as NCBI molecular databases. It does not cover OMIM, which the same page lists separately as copyrighted material. It does not, by itself, settle Bookshelf or GeneReviews.

NCBI Gene identifies a locus with a numeric GeneID. The symbol can change. The GeneID is the stable NCBI identifier. HGNC is the nomenclature authority for the symbol. Both should be stored. A match on symbol alone is not an identity match when the symbol has been reused or withdrawn.

RefSeq transcript and protein accessions are versioned (`NM_000110.4`, `NP_` accessions). Document 62 already says two versions are not interchangeable. This pass did not download a RefSeq release. The release identity for a future snapshot is the RefSeq release number plus the accession version, not “current RefSeq.”

Recommended role: molecular identity reference for GeneID and for RefSeq accessions that a snapshot actually contains. Not a clinical interpretation.

## MANE

The NCBI MANE page `https://www.ncbi.nlm.nih.gov/refseq/MANE/` was fetched.

MANE Select is one representative transcript per locus whose RefSeq and Ensembl/GENCODE records match in exon coordinates, coding sequence, and sequence, and which matches GRCh38. MANE Plus Clinical adds transcripts needed to report public pathogenic or likely pathogenic variants that the Select transcript does not cover. The page says mappings to GRCh37.p13 and to T2T-CHM13v2.0 exist, and that users must account for sequence differences. It says 64 genes in MANE v1.5 are annotated on patch accessions (`NW_` or `NT_`) because the primary GRCh38 sequence cannot represent them. The SHANK3 example is the page’s own.

The page says updates are rare and that the FTP site lists them. Releases are expected about yearly. Access routes named on the page are FTP in GFF3, GTF, FASTA, and GenBank flatfile, Entrez, NCBI Datasets, RefSeq GFF tags, and genome browsers. The FTP README itself was not opened. A separate license file was not opened. NCBI’s molecular-data policy is the closest fetched statement for the NCBI copy. The EMBL-EBI copy’s license was not separately fetched.

Recommended role: default transcript policy when the laboratory has not named a transcript, pinned to a MANE release. Not evidence that the patient’s tissue uses that transcript. Not a GRCh37 transcript until the mapping file for that release is stored and the sequence difference is visible.

## Ensembl

`https://www.ensembl.org/info/about/legal/disclaimer.html` timed out. Status: `failed`. No Ensembl license is claimed.

Ensembl stable IDs are versioned (`ENST00000311189.8` appears as an example on the MANE page). A future module may store the Ensembl identifier that MANE pairs with a RefSeq accession, because that pairing is on the MANE page. It should not download the full Ensembl regulation or variation build until the disclaimer and the release FTP are read.

Recommended role: none as a bulk dependency until the legal page and a release are fetched. The MANE pair is enough to record the matched Ensembl accession.

## UCSC Genome Browser

The UCSC data-use policy and the table browser were not opened. Status: `not_opened`.

UCSC is a browser and a redistribution point for many tracks. Each track has its own source and often its own restrictions. A UCSC table is not one license. Recommended role: none until a named track and that track’s terms are read. Not a second copy of RefSeq “because UCSC shows it.”

## HGNC

`https://www.genenames.org/about/` was fetched. HGNC approves one symbol per locus and issues a stable HGNC ID that remains when the symbol changes. The page says withdrawn phenotype symbols are no longer issued. The data-release paragraph says no restrictions are imposed on access to or use of HGNC data, and that HGNC gives no warranty.

The download index and the REST API were not opened. The about page is a use statement. It is not a file manifest. A future snapshot should still record the download URL, the date, and a checksum.

Recommended role: gene-symbol and HGNC-ID reference. The local knowledge base’s symbols should be checked against a pinned HGNC release rather than treated as already approved. Alias matching, which the ClinVar panel code does, can attach the wrong gene if an alias has moved. That check is not implemented.

## UniProt

`https://www.uniprot.org/help/license` returned a browser-fallback page, not the license. Status: `failed`. No UniProt license is claimed.

Protein accessions already printed on CPIC workbook rows, as document 31 describes, can be stored as citations of those workbook cells. They are not a UniProt dump. Recommended role: none as a bulk download until the license page is read. A protein accession that arrives inside a pinned CPIC or RefSeq record keeps the license of that record.

## Assemblies

GRCh37 and GRCh38 are NCBI reference assemblies. This pass did not download a FASTA or a checksum. Document 90 already refuses to guess a build.

Identity rule:

| Object | Required key |
|---|---|
| Gene | HGNC ID, and NCBI GeneID when a snapshot has it. Symbol is a label |
| Transcript | Accession with version, plus the annotation release |
| Protein | Accession with version |
| Small variant | Build, contig or RefSeq chromosome accession, left-aligned POS, REF, ALT, and the normalizer version. A second key may hold ClinVar’s right-shifted coordinates without overwriting the first |
| HGVS | Transcript or genomic accession with version, plus the HGVS string. The nomenclature site was not re-read |
| Assembly | Name plus the exact FASTA identifier or accession set. `hg19` is not stored as GRCh37 without an alias table |
| Allele, pharmacogenetic | PharmVar ID when PharmVar is licensed. Until then, the CPIC workbook gene, allele name, and workbook date. A star name alone is not the haplotype |
| Structural variant | Type, assembly, breakpoints or a stated imprecise interval, and the caller. An nsv is a cross-reference |

## Identifier mapping

Mappings go stale. The allowed mapping is a stored cross-reference with both identifiers and both versions. The following are not silent conversions:

- Symbol to a different HGNC ID after a symbol change.
- `NM_` version to the next version.
- GRCh37 coordinate to GRCh38 without a liftover record and a list of failures.
- ClinVar right-shifted allele to a left-aligned allele without the FASTA.
- Ensembl ID to RefSeq except for pairs that a pinned MANE release declares identical.
- rs identifier to a single ALT.

Unmapped fields stay on the raw record. They are not dropped because the internal schema has no column yet.

## Recommendation

Pin four identity sources before any new clinical rule: a HGNC release, a MANE release, a reference FASTA for each build the laboratory accepts, and the accession versions already printed on CPIC rows. Do not add a full Ensembl, UCSC, or UniProt mirror while their licenses are unread. Do not let `KNOWN_VARIANTS` remain the allele dictionary.
