"""Pet Care: track medication, measurements and stock for your pets."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .data import STORAGE_VERSION, PetCareData, storage_key
from .services import async_setup_services

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SENSOR]

type PetCareConfigEntry = ConfigEntry[PetCareData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions once, for all pets."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PetCareConfigEntry) -> bool:
    """Set up one pet."""
    # The pet's own device; each medication/measurement gets a device under it.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Pet Care",
        model="Pet",
    )
    data = PetCareData(hass, entry)
    await data.async_load()
    entry.runtime_data = data

    @callback
    def _tick(_now: datetime) -> None:
        # "Overdue" changes with time, not only when something is logged.
        data.async_notify()

    entry.async_on_unload(async_track_time_interval(hass, _tick, timedelta(minutes=1)))
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: PetCareConfigEntry) -> None:
    """Reload when medications/measurements are added, changed or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PetCareConfigEntry) -> bool:
    """Unload a pet."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete stored history when a pet is removed."""
    await Store(hass, STORAGE_VERSION, storage_key(entry.entry_id)).async_remove()
