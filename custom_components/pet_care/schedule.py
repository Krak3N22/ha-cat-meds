"""Schedule logic. Pure Python so it can be tested without Home Assistant."""

from __future__ import annotations

from datetime import datetime, time, timedelta

# A dose given up to this long before a scheduled time counts for that time.
EARLY_TOLERANCE = timedelta(hours=2)


def parse_times(value: str | list[str]) -> list[str]:
    """Parse "08:00, 20:00" into a sorted list of "HH:MM". Raises ValueError."""
    parts = value if isinstance(value, list) else value.replace(";", ",").split(",")
    result = set()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        parsed = datetime.strptime(part, "%H:%M").time()
        result.add(parsed.strftime("%H:%M"))
    return sorted(result)


def next_due(
    now: datetime,
    last: datetime | None,
    created: datetime,
    times: list[str],
    interval_days: float,
) -> datetime | None:
    """Return when the next dose/measurement is due, or None if unscheduled.

    With fixed times of day, the next due time is the first slot not covered by
    the last event (an event covers slots up to EARLY_TOLERANCE after it).
    Otherwise, with an interval, it is the last event plus the interval.
    A never-logged item is due at its first slot after creation, or right away.
    """
    tz = now.tzinfo
    if times:
        if last is not None:
            ref = last.astimezone(tz) + EARLY_TOLERANCE
        else:
            ref = created.astimezone(tz)
        slots = [time.fromisoformat(t) for t in times]
        for day_offset in range(3):
            day = ref.date() + timedelta(days=day_offset)
            for slot in slots:
                candidate = datetime.combine(day, slot, tzinfo=tz)
                if candidate > ref:
                    return candidate
        return None
    if interval_days:
        if last is None:
            return created.astimezone(tz)
        return last.astimezone(tz) + timedelta(days=interval_days)
    return None


def is_overdue(now: datetime, due: datetime | None) -> bool:
    """Return True if something was due and has not been done."""
    return due is not None and now >= due
