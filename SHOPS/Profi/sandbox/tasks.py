"""
Background task manager — profi_tasks table operations
"""
import asyncio
import json
import traceback
from datetime import datetime
from typing import Any, Callable, Coroutine
from uuid import UUID

from .db import get_pool
from .models import TaskResponse


async def create_task(task_type: str, params: dict | None = None) -> UUID:
    pool = get_pool()
    row = await pool.fetchrow(
        """INSERT INTO profi_tasks (task_type, status, params)
           VALUES ($1, 'pending', $2::jsonb)
           RETURNING id""",
        task_type,
        json.dumps(params) if params else None,
    )
    return row["id"]


async def update_task(
    task_id: UUID,
    *,
    status: str | None = None,
    progress: dict | None = None,
    result: dict | None = None,
    error: str | None = None,
):
    pool = get_pool()
    sets = []
    args = []
    idx = 1

    if status:
        sets.append(f"status = ${idx}")
        args.append(status)
        idx += 1
        if status == "running":
            sets.append("started_at = NOW()")
        elif status in ("completed", "failed"):
            sets.append("completed_at = NOW()")

    if progress is not None:
        sets.append(f"progress = ${idx}::jsonb")
        args.append(json.dumps(progress))
        idx += 1

    if result is not None:
        sets.append(f"result = ${idx}::jsonb")
        args.append(json.dumps(result))
        idx += 1

    if error is not None:
        sets.append(f"error = ${idx}")
        args.append(error)
        idx += 1

    if not sets:
        return

    args.append(task_id)
    await pool.execute(
        f"UPDATE profi_tasks SET {', '.join(sets)} WHERE id = ${idx}",
        *args,
    )


async def get_task(task_id: UUID) -> TaskResponse | None:
    pool = get_pool()
    row = await pool.fetchrow("SELECT * FROM profi_tasks WHERE id = $1", task_id)
    if not row:
        return None
    return TaskResponse(
        task_id=row["id"],
        task_type=row["task_type"],
        status=row["status"],
        progress=json.loads(row["progress"]) if row["progress"] else None,
        result=json.loads(row["result"]) if row["result"] else None,
        error=row["error"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )


async def get_running_tasks() -> list[TaskResponse]:
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT * FROM profi_tasks WHERE status IN ('pending', 'running') ORDER BY created_at"
    )
    result = []
    for row in rows:
        result.append(TaskResponse(
            task_id=row["id"],
            task_type=row["task_type"],
            status=row["status"],
            progress=json.loads(row["progress"]) if row["progress"] else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        ))
    return result


def launch_background_task(
    coro_factory: Callable[[UUID], Coroutine],
    task_id: UUID,
):
    """Launch a background asyncio task with automatic status updates."""

    async def _wrapper():
        try:
            await update_task(task_id, status="running")
            await coro_factory(task_id)
            await update_task(task_id, status="completed")
        except Exception as e:
            await update_task(task_id, status="failed", error=traceback.format_exc())

    asyncio.create_task(_wrapper())
