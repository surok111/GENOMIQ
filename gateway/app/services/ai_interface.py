from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AIService(Protocol):
    """Contract for the genomic interpretation engine (mock or real)."""

    async def interpret(self, raw_data: str) -> dict[str, Any]:
        """Interpret raw genomic data and return a JSON-serialisable result.

        Raises:
            ValueError: the input cannot be interpreted. This is permanent, so
                the worker does not retry it. Messages must never echo the input,
                because it is PHI.
        """
        ...
