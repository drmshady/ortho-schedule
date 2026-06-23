from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        msg = "datetime must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC)


def local_to_utc(local_date: date, local_time: time, timezone_name: str) -> datetime:
    local = datetime.combine(local_date, local_time, ZoneInfo(timezone_name))
    return local.astimezone(UTC)


def utc_to_local(value: datetime, timezone_name: str) -> datetime:
    return ensure_utc(value).astimezone(ZoneInfo(timezone_name))


def minutes_since_midnight(value: datetime, timezone_name: str) -> int:
    local = utc_to_local(value, timezone_name)
    return (local.hour * 60) + local.minute


def is_grid_aligned(value: datetime, grid_minutes: int, timezone_name: str) -> bool:
    if grid_minutes <= 0:
        msg = "grid_minutes must be positive"
        raise ValueError(msg)
    local = utc_to_local(value, timezone_name)
    return local.second == 0 and local.microsecond == 0 and minutes_since_midnight(
        value, timezone_name
    ) % grid_minutes == 0


def duration_is_grid_multiple(duration_minutes: int, grid_minutes: int) -> bool:
    return duration_minutes > 0 and grid_minutes > 0 and duration_minutes % grid_minutes == 0
