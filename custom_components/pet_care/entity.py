"""Base entity for Pet Care."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CONF_INTERVAL_DAYS, CONF_TIMES, DOMAIN, signal_update
from .data import PetCareData, ItemStatus


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
        self._attr_translation_placeholders = {"item": subentry.title}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Pet Care",
            model="Pet",
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
