"""Map a mock AI interpretation into a FHIR R4 genomics Bundle."""

from __future__ import annotations

import uuid
from typing import Any

from fhir.resources.bundle import Bundle
from pydantic import ValidationError

GENOMIC_REPORT_PROFILE = (
    "http://hl7.org/fhir/uv/genomics-reporting/StructureDefinition/genomic-report"
)
LOINC = "http://loinc.org"
V2_0074 = "http://terminology.hl7.org/CodeSystem/v2-0074"

VARIANT_ASSESSMENT = "69548-6"  # Genetic variant assessment
OVERALL_INTERPRETATION = "51968-6"  # Genetic disease analysis overall interpretation
GENETIC_ANALYSIS_REPORT = "51969-4"  # Genetic analysis report
CLINICAL_SIGNIFICANCE = "53037-8"  # Genetic variation clinical significance

# ClinVar-style risk-allele label used by the mock (not the 5-tier ACMG scale).
_ACMG_BY_RISK = {
    "High": "Risk factor",
    "Moderate": "Risk factor",
    "Normal": "Benign",
}


def build_fhir_bundle(ai_result: dict) -> dict:
    """Wrap an AI result dict in a validated FHIR R4 collection Bundle.

    The Patient is a generic placeholder. The AI result has no patient identity,
    and none is invented from the genomic payload.
    """
    gene, variant, genotype, risk = _required_fields(ai_result)

    patient_url = _urn()
    variant_url = _urn()
    overall_url = _urn()
    report_url = _urn()

    payload = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"fullUrl": patient_url, "resource": _patient(patient_url)},
            {
                "fullUrl": variant_url,
                "resource": _variant_observation(
                    patient_url, gene, variant, genotype, risk
                ),
            },
            {
                "fullUrl": overall_url,
                "resource": _overall_observation(patient_url, variant_url, risk),
            },
            {
                "fullUrl": report_url,
                "resource": _diagnostic_report(
                    patient_url,
                    gene,
                    genotype,
                    [variant_url, overall_url],
                ),
            },
        ],
    }

    try:
        bundle = Bundle.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"FHIR Bundle validation failed: {exc}") from exc
    return bundle.model_dump(mode="json")


def _required_fields(ai_result: dict) -> tuple[str, str, str, str]:
    if not isinstance(ai_result, dict):
        raise ValueError("AI result must be an object")
    gene = _nonempty_str(ai_result.get("gene"), "gene")
    genotype = _nonempty_str(ai_result.get("genotype"), "genotype")
    risk = _nonempty_str(ai_result.get("risk"), "risk")
    variant = ai_result.get("variant")
    variant_text = variant.strip() if isinstance(variant, str) else ""
    return gene, variant_text, genotype, risk


def _nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"AI result is missing {field}")
    return value.strip()


def _urn() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


def _patient(full_url: str) -> dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": full_url.removeprefix("urn:uuid:"),
        "identifier": [
            {
                "system": "urn:genomiq:patient",
                "value": "anonymous",
            }
        ],
    }


def _variant_observation(
    patient_url: str, gene: str, variant: str, genotype: str, risk: str
) -> dict[str, Any]:
    display = f"{gene} {variant}".strip()
    return {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": LOINC,
                    "code": VARIANT_ASSESSMENT,
                    "display": "Genetic variant assessment",
                }
            ],
            "text": display,
        },
        "subject": {"reference": patient_url},
        "valueCodeableConcept": {"text": genotype},
        "component": [
            {
                "code": {
                    "coding": [
                        {
                            "system": LOINC,
                            "code": CLINICAL_SIGNIFICANCE,
                            "display": "Genetic variation clinical significance",
                        }
                    ]
                },
                "valueCodeableConcept": {"text": _ACMG_BY_RISK.get(risk, "Risk factor")},
            }
        ],
    }


def _overall_observation(patient_url: str, variant_url: str, risk: str) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": LOINC,
                    "code": OVERALL_INTERPRETATION,
                    "display": "Genetic disease analysis overall interpretation",
                }
            ]
        },
        "subject": {"reference": patient_url},
        "valueCodeableConcept": {"text": risk},
        "derivedFrom": [{"reference": variant_url}],
    }


def _diagnostic_report(
    patient_url: str,
    gene: str,
    genotype: str,
    result_urls: list[str],
) -> dict[str, Any]:
    return {
        "resourceType": "DiagnosticReport",
        "meta": {"profile": [GENOMIC_REPORT_PROFILE]},
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": V2_0074,
                        "code": "LAB",
                        "display": "Laboratory",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": LOINC,
                    "code": GENETIC_ANALYSIS_REPORT,
                    "display": "Genetic analysis report",
                }
            ]
        },
        "subject": {"reference": patient_url},
        "conclusion": _conclusion(gene, genotype),
        "result": [{"reference": url} for url in result_urls],
    }


def _conclusion(gene: str, genotype: str) -> str:
    alleles = genotype.upper()
    if len(alleles) == 2 and alleles[0] == alleles[1]:
        zygosity = "Homozygous reference" if alleles == "CC" else "Homozygous variant"
    elif len(alleles) == 2:
        zygosity = "Heterozygous variant"
    else:
        zygosity = f"Genotype {genotype}"
    return f"{zygosity} detected in {gene}"
