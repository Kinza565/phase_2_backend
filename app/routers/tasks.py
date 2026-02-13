from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Task as TaskModel, User
from ..schemas.task import Task as TaskSchema, TaskComplete, TaskCreate, TaskUpdate
from .auth import get_current_user

router = APIRouter()


def _ensure_user_scope(user_id: str, current_user: User) -> None:
    if user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden",
        )


def _get_update_data(task_update: TaskUpdate) -> dict:
    if hasattr(task_update, "model_dump"):
        return task_update.model_dump(exclude_unset=True)
    return task_update.dict(exclude_unset=True)


@router.get("/{user_id}/tasks", response_model=List[TaskSchema])
def get_tasks(
    request: Request,
    user_id: str,
    skip: int = 0,
    limit: int = 100,
    status: str = "all",
    sort: str = "created_at",
    order: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all tasks for a user with optional filtering and sorting.

    @specs/features/task-crud.md
    """
    _ensure_user_scope(user_id, current_user)

    query = db.query(TaskModel).filter(TaskModel.user_id == current_user.id)

    if status == "completed":
        query = query.filter(TaskModel.completed.is_(True))
    elif status == "pending":
        query = query.filter(TaskModel.completed.is_(False))
    elif status != "all":
        raise HTTPException(status_code=422, detail="Invalid status filter")

    if sort == "title":
        query = query.order_by(TaskModel.title.asc() if order == "asc" else TaskModel.title.desc())
    elif sort == "created_at":
        query = query.order_by(TaskModel.created_at.asc() if order == "asc" else TaskModel.created_at.desc())
    else:
        raise HTTPException(status_code=422, detail="Invalid sort field")

    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="Invalid sort order")

    return query.offset(skip).limit(limit).all()


@router.post("/{user_id}/tasks", response_model=TaskSchema, status_code=status.HTTP_201_CREATED)
def create_task(
    request: Request,
    user_id: str,
    task: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new task for the user.

    @specs/features/task-crud.md
    """
    _ensure_user_scope(user_id, current_user)

    db_task = TaskModel(
        title=task.title,
        description=task.description,
        completed=task.completed,
        user_id=current_user.id,
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@router.get("/{user_id}/tasks/{task_id}", response_model=TaskSchema)
def get_task(
    request: Request,
    user_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific task by ID.

    @specs/features/task-crud.md
    """
    _ensure_user_scope(user_id, current_user)

    task = db.query(TaskModel).filter(TaskModel.id == task_id, TaskModel.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/{user_id}/tasks/{task_id}", response_model=TaskSchema)
def update_task(
    request: Request,
    user_id: str,
    task_id: str,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a specific task.

    @specs/features/task-crud.md
    """
    _ensure_user_scope(user_id, current_user)

    task = db.query(TaskModel).filter(TaskModel.id == task_id, TaskModel.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in _get_update_data(task_update).items():
        setattr(task, field, value)

    task.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{user_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    request: Request,
    user_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a specific task.

    @specs/features/task-crud.md
    """
    _ensure_user_scope(user_id, current_user)

    task = db.query(TaskModel).filter(TaskModel.id == task_id, TaskModel.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"detail": "Task deleted"}


@router.patch("/{user_id}/tasks/{task_id}/complete", response_model=TaskSchema)
def mark_task_complete(
    request: Request,
    user_id: str,
    task_id: str,
    payload: Optional[TaskComplete] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a task as complete.

    @specs/features/task-crud.md
    """
    _ensure_user_scope(user_id, current_user)

    task = db.query(TaskModel).filter(TaskModel.id == task_id, TaskModel.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.completed = True if payload is None else payload.completed
    task.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return task


# Backward-compatible endpoints (without user_id path)

@router.get("/tasks", response_model=List[TaskSchema])
def get_tasks_current_user(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    status: str = "all",
    sort: str = "created_at",
    order: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_tasks(
        request=request,
        user_id=str(current_user.id),
        skip=skip,
        limit=limit,
        status=status,
        sort=sort,
        order=order,
        current_user=current_user,
        db=db,
    )


@router.post("/tasks", response_model=TaskSchema, status_code=status.HTTP_201_CREATED)
def create_task_current_user(
    request: Request,
    task: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_task(
        request=request,
        user_id=str(current_user.id),
        task=task,
        current_user=current_user,
        db=db,
    )


@router.get("/tasks/{task_id}", response_model=TaskSchema)
def get_task_current_user(
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_task(
        request=request,
        user_id=str(current_user.id),
        task_id=task_id,
        current_user=current_user,
        db=db,
    )


@router.put("/tasks/{task_id}", response_model=TaskSchema)
def update_task_current_user(
    request: Request,
    task_id: str,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_task(
        request=request,
        user_id=str(current_user.id),
        task_id=task_id,
        task_update=task_update,
        current_user=current_user,
        db=db,
    )


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_current_user(
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return delete_task(
        request=request,
        user_id=str(current_user.id),
        task_id=task_id,
        current_user=current_user,
        db=db,
    )


@router.patch("/tasks/{task_id}/complete", response_model=TaskSchema)
def mark_task_complete_current_user(
    request: Request,
    task_id: str,
    payload: Optional[TaskComplete] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return mark_task_complete(
        request=request,
        user_id=str(current_user.id),
        task_id=task_id,
        payload=payload,
        current_user=current_user,
        db=db,
    )
