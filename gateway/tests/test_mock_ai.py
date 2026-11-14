import asyncio

import pytest

from app.core.config import settings
from app.services.ai_interface import AIService
from app.services.dependencies import get_ai_service
from app.services.mock_ai_service import MockAIService


@pytest.mark.parametrize(
    ("raw_data", "genotype", "risk"),
    [
        ("CT", "CT", "Moderate"),
        ("TT", "TT", "High"),
        ("CC", "CC", "Normal"),
        ("ct", "CT", "Moderate"),  # case-insensitive
        ("rs1801133:tt", "TT", "High"),  # marker embedded in a longer string
    ],
)
async def test_returns_expected_result(raw_data: str, genotype: str, risk: str) -> None:
    result = await MockAIService(delay=0).interpret(raw_data)

    assert result["gene"] == "MTHFR"
    assert result["genotype"] == genotype
    assert result["risk"] == risk
    assert result["mock"] is True


@pytest.mark.parametrize("raw_data", ["UNKNOWN", "", "   ", "AGAG"])
async def test_unknown_or_missing_genotype_raises(raw_data: str) -> None:
    with pytest.raises(ValueError, match="Unknown or missing genotype") as exc_info:
        await MockAIService(delay=0).interpret(raw_data)
    # PHI safety: the input must never be echoed in the error.
    assert raw_data.strip() == "" or raw_data not in str(exc_info.value)


async def test_simulates_processing_time(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    await MockAIService().interpret("CT")

    assert sleeps == [1.5]


async def test_results_are_independent_copies() -> None:
    service = MockAIService(delay=0)
    first = await service.interpret("CT")
    first["risk"] = "tampered"

    assert (await service.interpret("CT"))["risk"] == "Moderate"


def test_mock_satisfies_the_protocol() -> None:
    assert isinstance(MockAIService(), AIService)


async def test_get_ai_service_returns_mock_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "USE_MOCK_AI", True)
    assert isinstance(await get_ai_service(), MockAIService)


async def test_get_ai_service_without_mock_is_not_implemented_yet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "USE_MOCK_AI", False)
    with pytest.raises(NotImplementedError):
        await get_ai_service()
