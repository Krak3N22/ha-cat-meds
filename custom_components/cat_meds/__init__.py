"""Cat Meds: track medication, measurements and stock for your cats."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .data import STORAGE_VERSION, CatMedsData, storage_key

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SENSOR]

type CatMedsConfigEntry = ConfigEntry[CatMedsData]


async def async_setup_entry(hass: HomeAssistant, entry: CatMedsConfigEntry) -> bool:
    """Set up one cat."""
    data = CatMedsData(hass, entry)
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


async def _async_reload(hass: HomeAssistant, entry: CatMedsConfigEntry) -> None:
    """Reload when medications/measurements are added, changed or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CatMedsConfigEntry) -> bool:
    """Unload a cat."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete stored history when a cat is removed."""
    await Store(hass, STORAGE_VERSION, storage_key(entry.entry_id)).async_remove()
