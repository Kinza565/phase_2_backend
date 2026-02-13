from sqlmodel import Session, select
try:
    from .database import get_session
    from .models import Task
except ImportError:
    # For testing purposes when running directly
    from app.database import get_session
    from app.models import Task
import json

# Global variable to store current user ID (set by FastAPI endpoint)
_current_user_id = None

def set_current_user(user_id: str):
    """Set the current user ID for MCP tool operations."""
    global _current_user_id
    _current_user_id = user_id

def get_current_user_id() -> str:
    """Get the current user ID."""
    if not _current_user_id:
        raise ValueError("No user context set")
    return _current_user_id

def add_task(title: str, description: str = "") -> str:
    """Create a new task for the authenticated user."""
    user_id = get_current_user_id()

    with get_session() as session:
        task = Task(title=title, description=description, user_id=user_id)
        session.add(task)
        session.commit()
        session.refresh(task)
        return json.dumps({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed
        })

def list_tasks(status: str = "all", limit: int = 50) -> str:
    """List tasks for the authenticated user with optional filtering."""
    user_id = get_current_user_id()

    with get_session() as session:
        query = select(Task).where(Task.user_id == user_id)
        if status == "completed":
            query = query.where(Task.completed == True)
        elif status == "pending":
            query = query.where(Task.completed == False)

        tasks = session.exec(query.limit(limit)).all()
        return json.dumps([{
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed
        } for task in tasks])

def update_task(task_id: str, title: str = None, description: str = None, completed: bool = None) -> str:
    """Update an existing task."""
    user_id = get_current_user_id()

    with get_session() as session:
        task = session.exec(select(Task).where(Task.id == task_id, Task.user_id == user_id)).first()
        if not task:
            return json.dumps({"error": "Task not found"})

        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if completed is not None:
            task.completed = completed

        session.commit()
        session.refresh(task)
        return json.dumps({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed
        })

def delete_task(task_id: str) -> str:
    """Delete a task."""
    user_id = get_current_user_id()

    with get_session() as session:
        task = session.exec(select(Task).where(Task.id == task_id, Task.user_id == user_id)).first()
        if not task:
            return json.dumps({"error": "Task not found"})

        session.delete(task)
        session.commit()
        return json.dumps({"success": True, "message": "Task deleted"})

def complete_task(task_id: str) -> str:
    """Mark a task as complete."""
    user_id = get_current_user_id()

    with get_session() as session:
        task = session.exec(select(Task).where(Task.id == task_id, Task.user_id == user_id)).first()
        if not task:
            return json.dumps({"error": "Task not found"})

        task.completed = True
        session.commit()
        session.refresh(task)
        return json.dumps({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed
        })
