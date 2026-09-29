"""Readable logbook entries: "Freja got Inhaler from Lukas" instead of "Pressed"."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, EVENT_DOSE_GIVEN, EVENT_MEASUREMENT_LOGGED

# Logbook messages can't use strings.json, so they are translated here.
MESSAGES = {
    "en": {
        "dose": "got {item}",
        "dose_by": "got {item} from {user}",
        "measurement": "{item}: {value} {unit}",
        "measurement_by": "{item}: {value} {unit} (measured by {user})",
    },
    "sv": {
        "dose": "fick {item}",
        "dose_by": "fick {item} av {user}",
        "measurement": "{item}: {value} {unit}",
        "measurement_by": "{item}: {value} {unit} (mätt av {user})",
    },
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[Event], dict[str, Any]]], None
    ],
) -> None:
    """Describe Cat Meds events in the logbook."""
    lang = "sv" if hass.config.language.startswith("sv") else "en"
    messages = MESSAGES[lang]

    def _entity_id(platform: str, data: dict[str, Any], key: str) -> str | None:
        if "subentry_id" not in data:
            return None
        return er.async_get(hass).async_get_entity_id(
            platform, DOMAIN, f"{data['subentry_id']}_{key}"
        )

    @callback
    def describe_dose(event: Event) -> dict[str, Any]:
        data = event.data
        template = messages["dose_by" if data.get("user") else "dose"]
        return {
            LOGBOOK_ENTRY_NAME: data["cat"],
            LOGBOOK_ENTRY_MESSAGE: template.format(**data),
            LOGBOOK_ENTRY_ENTITY_ID: _entity_id("button", data, "give_dose"),
        }

    @callback
    def describe_measurement(event: Event) -> dict[str, Any]:
        data = event.data
        value = f"{data['value']:g}"
        if lang == "sv":
            value = value.replace(".", ",")
        template = messages["measurement_by" if data.get("user") else "measurement"]
        return {
            LOGBOOK_ENTRY_NAME: data["cat"],
            LOGBOOK_ENTRY_MESSAGE: template.format(
                **{**data, "value": value, "unit": data.get("unit", "")}
            ).replace("  ", " ").strip(),
            LOGBOOK_ENTRY_ENTITY_ID: _entity_id("number", data, "log_value"),
        }

    async_describe_event(DOMAIN, EVENT_DOSE_GIVEN, describe_dose)
    async_describe_event(DOMAIN, EVENT_MEASUREMENT_LOGGED, describe_measurement)
