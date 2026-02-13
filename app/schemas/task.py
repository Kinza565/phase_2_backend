from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TaskBase(BaseModel):
    """Base task schema with common fields.
    
    @specs/features/task-crud.md
    """
    title: str
    description: Optional[str] = None
    completed: bool = False

class TaskCreate(TaskBase):
    """Schema for creating new tasks."""
    pass

class TaskUpdate(BaseModel):
    """Schema for updating existing tasks."""
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class TaskComplete(BaseModel):
    """Schema for completing a task."""
    completed: bool = True

class Task(TaskBase):
    """Complete task schema with all fields."""
    id: str
    created_at: datetime
    updated_at: datetime
    user_id: str

    class Config:
        from_attributes = True

class TaskResponse(Task):
    """Task response schema for API responses."""
    pass
