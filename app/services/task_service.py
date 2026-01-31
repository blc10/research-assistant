from __future__ import annotations

from datetime import datetime

from ..db import execute, fetch_all, fetch_one
from ..utils import now_local, to_utc_iso


def create_task(title: str, due_at: datetime | None, source: str, notes: str | None = None) -> int:
    due_value = to_utc_iso(due_at) if due_at else None
    created_at = to_utc_iso(now_local())
    return execute(
        "INSERT INTO tasks(title, due_at, created_at, source, notes) VALUES (?, ?, ?, ?, ?)",
        (title, due_value, created_at, source, notes),
    )


def list_tasks(status: str = "pending", limit: int = 20) -> list[dict]:
    rows = fetch_all(
        "SELECT * FROM tasks WHERE status = ? ORDER BY due_at IS NULL, due_at ASC, created_at DESC LIMIT ?",
        (status, limit),
    )
    return [dict(row) for row in rows]


def count_tasks(status: str = "pending") -> int:
    row = fetch_one("SELECT COUNT(*) as total FROM tasks WHERE status = ?", (status,))
    return int(row["total"]) if row else 0


def list_tasks_between(start_iso: str, end_iso: str) -> list[dict]:
    rows = fetch_all(
        """
        SELECT * FROM tasks
        WHERE status = 'pending'
          AND due_at IS NOT NULL
          AND due_at BETWEEN ? AND ?
        ORDER BY due_at ASC
        """,
        (start_iso, end_iso),
    )
    return [dict(row) for row in rows]


def mark_done(task_id: int) -> bool:
    row = fetch_one("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not row:
        return False
    execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
    return True


def delete_task(task_id: int) -> bool:
    row = fetch_one("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not row:
        return False
    execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return True


def snooze_task(task_id: int, new_due_at: datetime) -> bool:
    row = fetch_one("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not row:
        return False
    execute("UPDATE tasks SET due_at = ?, reminded_at = NULL WHERE id = ?", (to_utc_iso(new_due_at), task_id))
    return True


def add_pending_task(chat_id: str, title: str, created_at_iso: str) -> int:
    return execute(
        "INSERT INTO pending_tasks(chat_id, title, created_at) VALUES (?, ?, ?)",
        (chat_id, title, created_at_iso),
    )


def get_pending_task(chat_id: str) -> dict | None:
    row = fetch_one(
        "SELECT * FROM pending_tasks WHERE chat_id = ? ORDER BY created_at DESC LIMIT 1",
        (chat_id,),
    )
    return dict(row) if row else None


def clear_pending_task(pending_id: int) -> None:
    execute("DELETE FROM pending_tasks WHERE id = ?", (pending_id,))


def due_tasks_for_reminder(now_iso: str) -> list[dict]:
    rows = fetch_all(
        """
        SELECT * FROM tasks
        WHERE status = 'pending'
          AND due_at IS NOT NULL
          AND reminded_at IS NULL
          AND due_at <= ?
        ORDER BY due_at ASC
        """,
        (now_iso,),
    )
    return [dict(row) for row in rows]


def set_reminded(task_id: int, reminded_at_iso: str) -> None:
    execute("UPDATE tasks SET reminded_at = ? WHERE id = ?", (reminded_at_iso, task_id))


def get_task(task_id: int) -> dict | None:
    row = fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    return dict(row) if row else None
