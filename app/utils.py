from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import load_config


CONFIG = load_config()


def get_tz() -> ZoneInfo:
    return ZoneInfo(CONFIG.timezone)


def now_local() -> datetime:
    return datetime.now(tz=get_tz())


def to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_tz())
    return dt.astimezone(ZoneInfo("UTC")).isoformat()


def from_iso_to_local(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(get_tz())


def format_dt_local(dt: datetime | None) -> str:
    if not dt:
        return "(zaman belirtilmedi)"
    return dt.strftime("%d %b %Y %H:%M")


def parse_time_str(value: str) -> time:
    parts = value.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return time(hour=hour, minute=minute, tzinfo=get_tz())


def end_of_week(base: datetime) -> datetime:
    # Sunday 23:59
    days_ahead = 6 - base.weekday()
    end = (base + timedelta(days=days_ahead)).replace(hour=23, minute=59, second=0, microsecond=0)
    return end


def end_of_month(base: datetime) -> datetime:
    # move to next month first day then back one minute
    if base.month == 12:
        next_month = base.replace(year=base.year + 1, month=1, day=1)
    else:
        next_month = base.replace(month=base.month + 1, day=1)
    end = next_month - timedelta(minutes=1)
    return end.replace(second=0, microsecond=0)
