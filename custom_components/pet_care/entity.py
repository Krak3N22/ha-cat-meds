"""Base entity for Pet Care."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_INTERVAL_DAYS,
    CONF_TIMES,
    DOMAIN,
    SUBENTRY_DOSE,
    SUBENTRY_MEASUREMENT,
    signal_update,
)
from .data import PetCareData, ItemStatus


MODELS = {SUBENTRY_DOSE: "Medication", SUBENTRY_MEASUREMENT: "Measurement"}


def has_schedule(subentry: ConfigSubentry) -> bool:
    """Return True if the item has a schedule."""
    return bool(subentry.data.get(CONF_TIMES) or subentry.data.get(CONF_INTERVAL_DAYS))


class PetCareEntity(Entity):
    """An entity belonging to one tracked item of one pet."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry, key: str) -> None:
        self._data: PetCareData = entry.runtime_data
        self._subentry = subentry
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_translation_key = key
        # One device per item, under the pet's device. A device can only
        # belong to one subentry, so items can't share the pet's device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=f"{entry.title} {subentry.title}",
            manufacturer="Pet Care",
            model=MODELS.get(subentry.subentry_type),
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def status(self) -> ItemStatus:
        """Current status of this entity's item."""
        return self._data.status(self._subentry)

    async def async_added_to_hass(self) -> None:
        """Refresh when data changes."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_update(self._data.entry.entry_id),
                self.async_write_ha_state,
            )
        )
