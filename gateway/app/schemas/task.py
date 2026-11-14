import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.db.models import TaskStatus


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    status: TaskStatus
    correlation_id: str | None = None
    attempts: int
    result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime