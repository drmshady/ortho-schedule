from datetime import date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src.core.timezone import duration_is_grid_multiple, is_grid_aligned
from src.services.availability_resolver import (
    Interval,
    covers,
    resolve_bookable_intervals,
)

CAIRO = "Africa/Cairo"


def _template(weekday: int, start: time, end: time) -> SimpleNamespace:
    return SimpleNamespace(weekday=weekday, start_local=start, end_local=end)


def _exception(d: date, kind: str, start: time | None, end: time | None) -> SimpleNamespace:
    return SimpleNamespace(date=d, kind=kind, start_local=start, end_local=end)


def _utc(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=ZoneInfo(CAIRO)).astimezone(
        ZoneInfo("UTC")
    )


def test_template_only_resolves_to_utc_interval() -> None:
    target = date(2026, 7, 6)  # Monday -> weekday 0
    intervals = resolve_bookable_intervals(
        target_date=target,
        timezone_name=CAIRO,
        templates=[_template(0, time(9, 0), time(13, 0))],
        exceptions=[],
    )
    assert intervals == [Interval(start=_utc(target, 9), end=_utc(target, 13))]


def test_wrong_weekday_template_is_ignored() -> None:
    target = date(2026, 7, 6)  # weekday 0
    intervals = resolve_bookable_intervals(
        target_date=target,
        timezone_name=CAIRO,
        templates=[_template(2, time(9, 0), time(13, 0))],
        exceptions=[],
    )
    assert intervals == []


def test_override_replaces_the_day() -> None:
    target = date(2026, 7, 6)
    intervals = resolve_bookable_intervals(
        target_date=target,
        timezone_name=CAIRO,
        templates=[_template(0, time(9, 0), time(17, 0))],
        exceptions=[_exception(target, "override", time(10, 0), time(12, 0))],
    )
    assert intervals == [Interval(start=_utc(target, 10), end=_utc(target, 12))]


def test_full_day_block_removes_all_availability() -> None:
    target = date(2026, 7, 6)
    intervals = resolve_bookable_intervals(
        target_date=target,
        timezone_name=CAIRO,
        templates=[_template(0, time(9, 0), time(17, 0))],
        exceptions=[_exception(target, "block", None, None)],
    )
    assert intervals == []


def test_partial_block_splits_interval() -> None:
    target = date(2026, 7, 6)
    intervals = resolve_bookable_intervals(
        target_date=target,
        timezone_name=CAIRO,
        templates=[_template(0, time(9, 0), time(17, 0))],
        exceptions=[_exception(target, "block", time(12, 0), time(13, 0))],
    )
    assert intervals == [
        Interval(start=_utc(target, 9), end=_utc(target, 12)),
        Interval(start=_utc(target, 13), end=_utc(target, 17)),
    ]


def test_extra_adds_and_merges_hours() -> None:
    target = date(2026, 7, 6)
    intervals = resolve_bookable_intervals(
        target_date=target,
        timezone_name=CAIRO,
        templates=[_template(0, time(9, 0), time(12, 0))],
        exceptions=[_exception(target, "extra", time(12, 0), time(14, 0))],
    )
    assert intervals == [Interval(start=_utc(target, 9), end=_utc(target, 14))]


def test_covers_requires_full_containment() -> None:
    target = date(2026, 7, 6)
    intervals = [Interval(start=_utc(target, 9), end=_utc(target, 12))]
    assert covers(intervals, _utc(target, 9), _utc(target, 10))
    assert not covers(intervals, _utc(target, 11), _utc(target, 13))
    assert not covers(intervals, _utc(target, 8), _utc(target, 9))


def test_grid_alignment_math() -> None:
    target = date(2026, 7, 6)
    assert is_grid_aligned(_utc(target, 9, 0), 15, CAIRO)
    assert is_grid_aligned(_utc(target, 9, 15), 15, CAIRO)
    assert not is_grid_aligned(_utc(target, 9, 7), 15, CAIRO)
    assert duration_is_grid_multiple(30, 15)
    assert not duration_is_grid_multiple(20, 15)
    assert not duration_is_grid_multiple(0, 15)
