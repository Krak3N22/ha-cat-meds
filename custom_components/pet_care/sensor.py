"""Sensors: last time, next due time and last measured value."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PetCareConfigEntry
from .const import CONF_UNIT, SUBENTRY_DOSE, SUBENTRY_MEASUREMENT
from .entity import PetCareEntity, has_schedule


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PetCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    for subentry in entry.subentries.values():
        entities: list[SensorEntity] = []
        if subentry.subentry_type == SUBENTRY_DOSE:
            entities.append(LastSensor(entry, subentry, "last_given"))
            entities.append(LastBySensor(entry, subentry, "last_given_by"))
        elif subentry.subentry_type == SUBENTRY_MEASUREMENT:
            entities.append(LastSensor(entry, subentry, "last_measured"))
            entities.append(LastBySensor(entry, subentry, "last_measured_by"))
            entities.append(ValueSensor(entry, subentry, "value"))
        if has_schedule(subentry):
            entities.append(NextDueSensor(entry, subentry, "next_due"))
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)


class LastSensor(PetCareEntity, SensorEntity):
    """When it was last done, and by whom."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:history"

    @property
    def native_value(self) -> datetime | None:
        return self.status.last

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"by": self.status.last_by}


class LastBySensor(PetCareEntity, SensorEntity):
    """Who did it last."""

    _attr_icon = "mdi:account-check"

    @property
    def native_value(self) -> str | None:
        return self.status.last_by


class NextDueSensor(PetCareEntity, SensorEntity):
    """When it is due next."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> datetime | None:
        return self.status.next_due


class ValueSensor(PetCareEntity, SensorEntity):
    """Last measured value, with history graph."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"

    def __init__(self, entry, subentry, key) -> None:
        super().__init__(entry, subentry, key)
        self._attr_native_unit_of_measurement = subentry.data.get(CONF_UNIT) or None

    @property
    def native_value(self) -> float | None:
        return self.status.last_value
