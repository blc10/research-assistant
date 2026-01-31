from __future__ import annotations

from datetime import datetime, timedelta

from ..db import fetch_all
from ..utils import from_iso_to_local, get_tz


def get_read_streak() -> int:
    rows = fetch_all("SELECT read_at FROM reads ORDER BY read_at DESC")
    if not rows:
        return 0

    dates = sorted({from_iso_to_local(row["read_at"]).date() for row in rows}, reverse=True)
    if not dates:
        return 0

    streak = 0
    today = datetime.now(tz=get_tz()).date()
    expected = today

    for day in dates:
        if day == expected:
            streak += 1
            expected = expected - timedelta(days=1)
        elif day < expected:
            # gap
            break
    return streak
