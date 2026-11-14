import pytest
from fhir.resources.bundle import Bundle
from pydantic import ValidationError

from app.services.fhir_mapper import (
    GENETIC_ANALYSIS_REPORT,
    GENOMIC_REPORT_PROFILE,
    OVERALL_INTERPRETATION,
    VARIANT_ASSESSMENT,
    build_fhir_bundle,
)

TT_RESULT = {
    "gene": "MTHFR",
    "variant": "C677T",
    "rsid": "rs1801133",
    "genotype": "TT",
    "risk": "High",
    "interpretation": "Homozygous variant: substantially reduced MTHFR enzyme activity.",
}


def _resources(bundle: dict) -> list[dict]:
    return [entry["resource"] for entry in bundle["entry"]]


def _by_type(bundle: dict, resource_type: str) -> list[dict]:
    return [resource for resource in _resources(bundle) if resource["resourceType"] == resource_type]


def _full_url(bundle: dict, resource: dict) -> str:
    for entry in bundle["entry"]:
        if entry["resource"] is resource:
            return entry["fullUrl"]
    raise AssertionError("resource is not an entry in the bundle")


def test_build_fhir_bundle_returns_a_valid_collection() -> None:
    bundle = build_fhir_bundle(TT_RESULT)

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    # Round-trip: the mapper already validated, and the dumped JSON still does.
    Bundle.model_validate(bundle)

    types = [resource["resourceType"] for resource in _resources(bundle)]
    assert types.count("Patient") == 1
    assert types.count("Observation") == 2
    assert types.count("DiagnosticReport") == 1


def test_variant_and_overall_observations_carry_genotype_and_risk() -> None:
    bundle = build_fhir_bundle(TT_RESULT)
    observations = _by_type(bundle, "Observation")

    variant = next(
        obs for obs in observations if obs["code"]["coding"][0]["code"] == VARIANT_ASSESSMENT
    )
    overall = next(
        obs
        for obs in observations
        if obs["code"]["coding"][0]["code"] == OVERALL_INTERPRETATION
    )

    assert variant["valueCodeableConcept"]["text"] == "TT"
    assert variant["component"][0]["valueCodeableConcept"]["text"] == "Risk factor"
    assert overall["valueCodeableConcept"]["text"] == "High"
    assert overall["derivedFrom"] == [{"reference": _full_url(bundle, variant)}]


def test_diagnostic_report_links_both_observations() -> None:
    bundle = build_fhir_bundle(TT_RESULT)
    report = _by_type(bundle, "DiagnosticReport")[0]
    observation_urls = {
        entry["fullUrl"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    }

    assert report["meta"]["profile"] == [GENOMIC_REPORT_PROFILE]
    assert report["status"] == "final"
    assert report["category"][0]["coding"][0]["code"] == "LAB"
    assert report["code"]["coding"][0]["code"] == GENETIC_ANALYSIS_REPORT
    assert report["conclusion"] == "Homozygous variant detected in MTHFR"
    assert {item["reference"] for item in report["result"]} == observation_urls


@pytest.mark.parametrize(
    "ai_result",
    [
        {},
        {"gene": "MTHFR"},
        {"gene": "MTHFR", "genotype": "TT"},
        {"gene": " ", "genotype": "TT", "risk": "High"},
        "not-a-dict",
    ],
)
def test_invalid_ai_result_raises_value_error(ai_result: object) -> None:
    with pytest.raises(ValueError):
        build_fhir_bundle(ai_result)  # type: ignore[arg-type]


def test_fhir_validation_failure_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(_payload: object) -> Bundle:
        raise ValidationError.from_exception_data(
            "Bundle",
            [{"type": "missing", "loc": ("type",), "msg": "Field required", "input": {}}],
        )

    monkeypatch.setattr(
        "app.services.fhir_mapper.Bundle.model_validate",
        reject,
    )

    with pytest.raises(ValueError, match="FHIR Bundle validation failed"):
        build_fhir_bundle(TT_RESULT)
