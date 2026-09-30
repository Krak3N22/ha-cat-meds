"""Tests for the pure schedule logic (no Home Assistant needed)."""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# Load schedule.py directly so the tests don't import Home Assistant.
_path = Path(__file__).parents[1] / "custom_components/pet_care/schedule.py"
_spec = importlib.util.spec_from_file_location("schedule", _path)
schedule = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schedule)

TZ = ZoneInfo("Europe/Stockholm")
TIMES = ["08:00", "20:00"]
CREATED = datetime(2026, 9, 1, 12, 0, tzinfo=TZ)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=TZ)


def test_parse_times():
    assert schedule.parse_times("20:00, 8:00,,08:00") == ["08:00", "20:00"]
    assert schedule.parse_times("") == []
    with pytest.raises(ValueError):
        schedule.parse_times("8 am")


def test_never_given_due_at_first_slot_after_creation():
    assert schedule.next_due(at(1, 13), None, CREATED, TIMES, 0) == at(1, 20)


def test_given_evening_next_is_morning():
    assert schedule.next_due(at(2, 21), at(2, 20, 15), CREATED, TIMES, 0) == at(3, 8)


def test_given_a_bit_early_counts():
    assert schedule.next_due(at(2, 19), at(2, 18, 30), CREATED, TIMES, 0) == at(3, 8)


def test_missed_morning_is_overdue():
    now = at(3, 10)
    due = schedule.next_due(now, at(2, 20), CREATED, TIMES, 0)
    assert due == at(3, 8)
    assert schedule.is_overdue(now, due)


def test_late_morning_dose_moves_to_evening():
    assert schedule.next_due(at(3, 10), at(3, 10), CREATED, TIMES, 0) == at(3, 20)


def test_interval_weekly():
    last = at(1, 18)
    assert schedule.next_due(at(2, 9), last, CREATED, [], 7) == last + timedelta(days=7)


def test_interval_never_measured_is_due_now():
    now = at(2, 9)
    due = schedule.next_due(now, None, CREATED, [], 7)
    assert schedule.is_overdue(now, due)


def test_no_schedule():
    due = schedule.next_due(at(2, 9), None, CREATED, [], 0)
    assert due is None
    assert not schedule.is_overdue(at(2, 9), due)


def test_doses_per_day():
    assert schedule.doses_per_day(["08:00", "20:00"], 0) == 2
    assert schedule.doses_per_day([], 7) == pytest.approx(1 / 7)
    assert schedule.doses_per_day([], 0) is None


def test_days_left():
    assert schedule.days_left(200, 1, 1) == 200
    assert schedule.days_left(30, 0.5, 2) == 30
    assert schedule.days_left(10, 1, 1 / 7) == pytest.approx(70)
    assert schedule.days_left(10, 1, None) is None
    assert schedule.days_left(10, 0, 1) is None
