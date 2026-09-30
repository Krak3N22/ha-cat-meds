"""Tests for readable logbook entries."""

from __future__ import annotations

from typing import Any

from homeassistant.core import Event, HomeAssistant

from custom_components.pet_care import logbook
from custom_components.pet_care.const import (
    DOMAIN,
    EVENT_DOSE_GIVEN,
    EVENT_MEASUREMENT_LOGGED,
    EVENT_UNDONE,
)


def _describers(hass: HomeAssistant) -> dict[str, Any]:
    found: dict[str, Any] = {}

    def register(domain: str, event_type: str, describe) -> None:
        assert domain == DOMAIN
        found[event_type] = describe

    logbook.async_describe_events(hass, register)
    return found


async def test_logbook_english(hass: HomeAssistant) -> None:
    """Entries read like sentences."""
    hass.config.language = "en"
    describe = _describers(hass)

    entry = describe[EVENT_DOSE_GIVEN](
        Event(EVENT_DOSE_GIVEN, {"pet": "Freja", "item": "Inhaler", "user": "Alex"})
    )
    assert entry["name"] == "Freja"
    assert entry["message"] == "got Inhaler from Alex"

    entry = describe[EVENT_MEASUREMENT_LOGGED](
        Event(
            EVENT_MEASUREMENT_LOGGED,
            {"pet": "Phoenix", "item": "Glucose", "value": 6.5, "unit": "mmol/L", "user": None},
        )
    )
    assert entry["message"] == "Glucose: 6.5 mmol/L"


async def test_logbook_swedish(hass: HomeAssistant) -> None:
    """Swedish servers get Swedish entries with decimal commas."""
    hass.config.language = "sv"
    describe = _describers(hass)

    entry = describe[EVENT_DOSE_GIVEN](
        Event(EVENT_DOSE_GIVEN, {"pet": "Freja", "item": "Inhalator", "user": "Alex"})
    )
    assert entry["message"] == "fick Inhalator av Alex"

    entry = describe[EVENT_MEASUREMENT_LOGGED](
        Event(
            EVENT_MEASUREMENT_LOGGED,
            {"pet": "Phoenix", "item": "Blodsocker", "value": 6.5, "unit": "", "user": "Alex"},
        )
    )
    assert entry["message"] == "Blodsocker: 6,5 (mätt av Alex)"

    entry = describe[EVENT_UNDONE](
        Event(
            EVENT_UNDONE,
            {
                "pet": "Freja",
                "item": "Inhalator",
                "user": "Alex",
                "undone_at": "2020-01-01T12:00:00+00:00",
            },
        )
    )
    assert entry["message"].startswith("Inhalator från kl. 2020-01-01")
    assert entry["message"].endswith("ångrades av Alex")
