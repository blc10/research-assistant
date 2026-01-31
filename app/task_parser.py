from __future__ import annotations

import re
from datetime import datetime

import dateparser
from dateparser.search import search_dates

from .utils import end_of_month, end_of_week, get_tz


TASK_KEYWORDS = {
    "hatırlat",
    "hatirlat",
    "toplantı",
    "toplanti",
    "deadline",
    "bitir",
    "yap",
    "görev",
    "gorev",
    "ödev",
    "odev",
    "tez",
    "thesis",
    "proposal",
    "sunum",
    "makale",
    "okuma",
    "okumak",
}


def _strip_filler(text: str) -> str:
    cleaned = re.sub(r"\b(hatırlat|hatirlat|lütfen|lutfen)\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_task_text(text: str, now: datetime) -> tuple[str, datetime | None]:
    tz = get_tz()
    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": now,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": tz.key,
    }

    found = search_dates(text, languages=["tr"], settings=settings)
    due_at = None
    cleaned = text

    if found:
        # take the last date-like phrase
        phrase, dt = found[-1]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        due_at = dt
        cleaned = text.replace(phrase, " ").strip()

    lowered = text.lower()
    if due_at is None:
        if "bu hafta" in lowered or "this week" in lowered:
            due_at = end_of_week(now)
        elif "bu ay" in lowered or "this month" in lowered:
            due_at = end_of_month(now)

    title = _strip_filler(cleaned) if cleaned else text.strip()
    return title, due_at


def looks_like_task(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in TASK_KEYWORDS)


def parse_duration(text: str) -> int | None:
    # returns minutes
    match = re.search(r"(\d+)\s*(dakika|dk|saat|gün|gun)", text.lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit in {"dakika", "dk"}:
        return value
    if unit == "saat":
        return value * 60
    if unit in {"gün", "gun"}:
        return value * 60 * 24
    return None
