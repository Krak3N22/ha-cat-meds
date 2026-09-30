"""Binary sensor that turns on when a dose or measurement is overdue."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PetCareConfigEntry
from .const import CONF_TRACK_STOCK, SUBENTRY_DOSE
from .entity import PetCareEntity, has_schedule


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PetCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up overdue sensors."""
    for subentry in entry.subentries.values():
        entities: list[BinarySensorEntity] = []
        if has_schedule(subentry):
            entities.append(OverdueSensor(entry, subentry, "overdue"))
        if subentry.subentry_type == SUBENTRY_DOSE and subentry.data.get(
            CONF_TRACK_STOCK
        ):
            entities.append(LowStockSensor(entry, subentry, "low_stock"))
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)


class OverdueSensor(PetCareEntity, BinarySensorEntity):
    """On when the item is due and has not been done."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.status.overdue


class LowStockSensor(PetCareEntity, BinarySensorEntity):
    """On when the stock runs out within the warning time."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:package-variant-remove"

    @property
    def is_on(self) -> bool:
        return self.status.low_stock
