import asyncio
from typing import Any, Final

_DISCLAIMER: Final = "Mock result for development only; not for clinical use"

# Order matters: the first marker found in the input wins (CT, then TT, then CC).
_RESULTS: Final[tuple[tuple[str, dict[str, Any]], ...]] = (
    (
        "CT",
        {
            "gene": "MTHFR",
            "variant": "C677T",
            "rsid": "rs1801133",
            "genotype": "CT",
            "risk": "Moderate",
            "interpretation": "Heterozygous: mildly reduced MTHFR enzyme activity.",
        },
    ),
    (
        "TT",
        {
            "gene": "MTHFR",
            "variant": "C677T",
            "rsid": "rs1801133",
            "genotype": "TT",
            "risk": "High",
            "interpretation": "Homozygous variant: substantially reduced MTHFR enzyme activity.",
        },
    ),
    (
        "CC",
        {
            "gene": "MTHFR",
            "variant": "C677T",
            "rsid": "rs1801133",
            "genotype": "CC",
            "risk": "Normal",
            "interpretation": "Homozygous reference: typical MTHFR enzyme activity.",
        },
    ),
)


class MockAIService:
    """Deterministic stand-in for the AI engine. Implements `AIService`."""

    def __init__(self, delay: float = 1.5) -> None:
        # `delay` exists so tests can run without waiting; the default is the spec value.
        self._delay = delay

    async def interpret(self, raw_data: str) -> dict[str, Any]:
        await asyncio.sleep(self._delay)  # simulate processing time

        normalized = raw_data.upper()
        for marker, template in _RESULTS:
            if marker in normalized:
                # Fresh dict per call so callers can never mutate shared state.
                return {**template, "mock": True, "disclaimer": _DISCLAIMER}

        # Deliberately does not include raw_data (PHI) in the message.
        raise ValueError("Unknown or missing genotype")
