from __future__ import annotations

from datetime import datetime

from ..db import execute, fetch_all
from ..utils import now_local, to_utc_iso


def create_goal(title: str, year: int) -> int:
    created_at = to_utc_iso(now_local())
    return execute(
        "INSERT INTO goals(title, year, created_at) VALUES (?, ?, ?)",
        (title, year, created_at),
    )


def list_goals(status: str = "active") -> list[dict]:
    rows = fetch_all(
        "SELECT * FROM goals WHERE status = ? ORDER BY year DESC, created_at DESC",
        (status,),
    )
    return [dict(row) for row in rows]


def update_progress(goal_id: int, progress: int) -> None:
    execute("UPDATE goals SET progress = ? WHERE id = ?", (progress, goal_id))


def complete_goal(goal_id: int) -> None:
    execute("UPDATE goals SET status = 'done', progress = 100 WHERE id = ?", (goal_id,))
