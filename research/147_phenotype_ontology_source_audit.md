# 147. Phenotype ontology source audit

Accessed 23 November 2026. Historical reports have to keep the ontology version they were coded with. A later release may replace a term. The old identifier remains the meaning of the old report.

## HPO

The Human Phenotype Ontology README on GitHub was fetched. It says the download URLs are `http://purl.obolibrary.org/obo/hp.obo` and `http://purl.obolibrary.org/obo/hp.owl`, and that the official PURL is the OWL form. It points the license and the citation to `https://hpo.jax.org/app/license`. That license page was not opened. Status of the license: `not_opened`. A third-party table that calls HPO CC0 is not used.

No HPO release number was read, because the ontology file was not downloaded. Document 93 already requires a pin before any phenotype rank. That requirement stands, and it now has a second gate: the license page has to be read before the file is stored for redistribution.

What HPO provides, as an ontology, once a release is pinned:

- Stable identifiers of the form `HP:` plus seven digits.
- Parent-child relations. A child is more specific. The true-path convention is a property of how the ontology is used, and document 93 already limits it.
- Obsolete terms, which a release marks, often with a replacement. Only the replacement field in that release may be followed.
- A separate disease-annotation file, conventionally `phenotype.hpoa`. It was not downloaded. Annotations are not the ontology. They have their own version and they are not diagnostic criteria unless a pin says so.

Recommended role: phenotype ontology for the review aid, blocked until the license page is fetched and accepted. Not a disease classification and not a gene-disease validity source.

Historical reports store the HPO identifier, the term label at that release, and the release identifier. If a later release obsoletes the term, the report still shows the original identifier and label, plus a note that the current release maps it. The report is not rewritten.

## MONDO

The OBO Foundry record `https://obofoundry.org/ontology/mondo.html` was fetched. It states the license as CC BY 4.0, the PURL `http://purl.obolibrary.org/obo/mondo.owl`, and the repository `https://github.com/monarch-initiative/mondo`. Products listed are `mondo.owl`, `mondo.obo`, `mondo.json`, a base release, and a simple release. Mappings are in SSSOM on that GitHub path and also as cross-references inside the release. The record says Mondo harmonizes OMIM, Orphanet, EFO, the Disease Ontology, ICD-11 Foundation, and the NCIt neoplasm branch, and that it tracks provenance for integrated parts.

The OWL file itself was not downloaded. The Foundry page is a registry record, not the ontology bytes. The license line on that record is the statement used here. The OWL header should be checked when the file is first snapshotted, because a registry line can lag a file.

Recommended role: disease-identity crosswalk. A Mondo ID can link an Orphanet code, an OMIM number, and a Disease Ontology ID without copying OMIM text. The OMIM number inside a mapping is an identifier, not a license to store the OMIM entry. Not a validity source and not a phenotype source.

## Disease Ontology

The Disease Ontology license and release were not opened. Status: `not_opened`.

Mondo already states that it integrates the Disease Ontology. Until the Disease Ontology’s own license is read, GenomIQ should consume DO identifiers only as cross-references inside a pinned Mondo file, under Mondo’s CC BY terms, and should not ship a separate DO product.

Recommended role: none as an independent download.

## SNOMED CT

The SNOMED license and the National Library of Medicine distribution terms were not opened. Status: `not_opened`.

SNOMED is a clinical terminology with affiliate licensing in most uses. Free public access to a browser is not permission to put SNOMED identifiers and terms into a customer deployment. Recommended role: none. Do not map HPO to SNOMED inside the product until a license is held. A future interface can display a SNOMED code that a hospital system already sent, as a customer-supplied identifier, without embedding the SNOMED release.

## Other vocabularies

| Vocabulary | Opened | Role |
|---|---|---|
| Sequence Ontology | No | Needed later as the consequence vocabulary of a pinned annotator. Not downloaded |
| GENO, for zygosity | No. A Phenopackets page in an earlier task named it | Not adopted |
| Mondo-to-HPO links | No file opened | A crosswalk has to be versioned on both sides |
| ORDO | Named in the Orphadata FAQ as a described product | The FAQ distinguishes Science files from Products. ORDO’s own license line was not read. Do not assume the FAQ’s CC BY sentence covers every Orphanet product |

## Hierarchies, obsolescence, and mappings

A hierarchy is usable only inside one pinned release. Parent identifiers are stored as edges with that release’s identifier. They are not recomputed from a newer file when an old report is rendered.

Obsolete terms are a first-class state. The loader records `obsolete`, `replaced_by` or the release’s equivalent field, and leaves the old identifier in place. A term with no replacement is `obsolete_unmapped`. It is not dropped.

Cross-ontology mappings are their own artifact: source release, target release, mapping method, and mapping file checksum. A Mondo cross-reference and an HPO annotation are not the same mapping and must not be stored in one undifferentiated “disease code” column.

## Versioning and historical reports

| Event | Behavior |
|---|---|
| New HPO release | Store it beside the old release. Do not delete the old file |
| Term obsoleted | New coding uses the replacement only after a person or a reviewed rule accepts it. Old reports keep the original |
| Label edited, identifier unchanged | The report shows the label from its own release. A current label may be shown next to it and marked current |
| Disease annotation file changes | Phenotype overlap results are recomputed only for a new analysis. A signed report keeps the overlap table it was signed with |
| Mapping added or removed | The old mapping snapshot remains. Conflict between two mapping releases is a conflict record, not a silent overwrite |

Missing phenotype information is handled in document 93. This document only says that the ontology file is not a substitute for a patient term list.

## License gate

| Source | License statement retrieved | Redistribution |
|---|---|---|
| HPO | Not retrieved. README points at a license URL | Blocked |
| MONDO | CC BY 4.0 on the OBO Foundry record | Allowed only with attribution, once the OWL header matches. Indicate modifications |
| Disease Ontology | Not retrieved | Blocked as a separate product |
| SNOMED CT | Not retrieved | Blocked |
| Orphanet disease names inside Orphadata Science | CC BY 4.0 on the FAQ, for Science products | Allowed with the citation in document 146. Products remain blocked |

## Recommendation

Use Mondo, after the file header is checked, as the disease identifier. Use HPO as the phenotype identifier only after its license page is read. Keep every report tied to the release it used. Do not embed SNOMED.
