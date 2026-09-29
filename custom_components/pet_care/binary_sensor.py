"""Binary sensor that turns on when a dose or measurement is overdue."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PetCareConfigEntry
from .entity import PetCareEntity, has_schedule


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PetCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up overdue sensors."""
    for subentry in entry.subentries.values():
        if has_schedule(subentry):
            async_add_entities(
                [OverdueSensor(entry, subentry, "overdue")],
                config_subentry_id=subentry.subentry_id,
            )


class OverdueSensor(PetCareEntity, BinarySensorEntity):
    """On when the item is due and has not been done."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.status.overdue
