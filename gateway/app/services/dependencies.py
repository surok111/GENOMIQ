from app.core.config import settings
from app.services.ai_interface import AIService
from app.services.mock_ai_service import MockAIService


async def get_ai_service() -> AIService:
    """Return the configured AI service.

    Async on purpose: FastAPI runs sync dependencies in a threadpool, and the
    worker can simply `await` it. Used as a FastAPI dependency and called
    directly by the worker.
    """
    if settings.USE_MOCK_AI:
        return MockAIService()
    # Future: return RealAIService()
    raise NotImplementedError("Real AI service is not implemented yet")
