from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional
from uuid import uuid4

class Task(SQLModel, table=True):
    """Task model for todo items.
    
    @specs/features/task-crud.md
    """
    __tablename__ = "tasks"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str
    description: Optional[str] = None
    completed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: str = Field(foreign_key="users.id")

    # Relationship back to user
    user: Optional["User"] = Relationship(back_populates="tasks")


