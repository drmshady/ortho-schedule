"""Pure availability resolution: weekly template + date exceptions -> bookable UTC intervals.

Resolution order (data-model.md): weekday template intervals -> apply ``override`` (replaces
the day) -> subtract ``block`` intervals -> add ``extra`` intervals. The result is the set of
bookable center-local intervals converted to UTC. This module has no database dependency so it
can be unit-tested directly.
"""
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, time
from typing import Protocol

from src.core.timezone import local_to_utc


class TemplateRow(Protocol):
    weekday: int
    start_local: time
    end_local: time


class ExceptionRow(Protocol):
    date: date_type
    kind: str
    start_local: time | None
    end_local: time | None


@dataclass(frozen=True)
class Interval:
    """A bookable interval, in UTC."""

    start: datetime
    end: datetime


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _to_local_minutes(rows: Iterable[tuple[time, time]]) -> list[tuple[int, int]]:
    return [(_minutes(s), _minutes(e)) for s, e in rows if _minutes(e) > _minutes(s)]


def _merge(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _subtract(base: list[tuple[int, int]], cut: tuple[int, int]) -> list[tuple[int, int]]:
    cut_start, cut_end = cut
    result: list[tuple[int, int]] = []
    for start, end in base:
        if cut_end <= start or cut_start >= end:
            result.append((start, end))
            continue
        if cut_start > start:
            result.append((start, cut_start))
        if cut_end < end:
            result.append((cut_end, end))
    return result


def resolve_bookable_intervals(
    *,
    target_date: date_type,
    timezone_name: str,
    templates: Sequence[TemplateRow],
    exceptions: Sequence[ExceptionRow],
) -> list[Interval]:
    """Resolve the bookable UTC intervals for one doctor on ``target_date``."""
    day_exceptions = [e for e in exceptions if e.date == target_date]
    overrides = [e for e in day_exceptions if e.kind == "override"]
    blocks = [e for e in day_exceptions if e.kind == "block"]
    extras = [e for e in day_exceptions if e.kind == "extra"]

    if overrides:
        local = _to_local_minutes(
            (e.start_local, e.end_local) for e in overrides if e.start_local and e.end_local
        )
    else:
        local = _to_local_minutes(
            (t.start_local, t.end_local) for t in templates if t.weekday == target_date.weekday()
        )

    local = _merge(local)

    for block in blocks:
        if block.start_local is None or block.end_local is None:
            local = []  # full-day block removes all availability
            break
        local = _subtract(local, (_minutes(block.start_local), _minutes(block.end_local)))

    for extra in extras:
        if extra.start_local and extra.end_local:
            local.append((_minutes(extra.start_local), _minutes(extra.end_local)))

    local = _merge(local)

    intervals: list[Interval] = []
    for start_min, end_min in local:
        start = local_to_utc(target_date, time(start_min // 60, start_min % 60), timezone_name)
        end = local_to_utc(target_date, time(end_min // 60, end_min % 60), timezone_name)
        intervals.append(Interval(start=start, end=end))
    return intervals


def covers(intervals: Sequence[Interval], start: datetime, end: datetime) -> bool:
    """True when ``[start, end)`` lies fully within a single bookable interval."""
    return any(iv.start <= start and end <= iv.end for iv in intervals)
