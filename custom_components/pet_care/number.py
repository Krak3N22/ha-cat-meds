"""Numbers: editable stock, and an input box for logging measurements."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PetCareConfigEntry
from .const import CONF_TRACK_STOCK, CONF_UNIT, SUBENTRY_DOSE, SUBENTRY_MEASUREMENT
from .entity import PetCareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PetCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_DOSE and subentry.data.get(
            CONF_TRACK_STOCK
        ):
            async_add_entities(
                [StockNumber(entry, subentry, "stock")],
                config_subentry_id=subentry.subentry_id,
            )
        elif subentry.subentry_type == SUBENTRY_MEASUREMENT:
            async_add_entities(
                [LogValueNumber(entry, subentry, "log_value")],
                config_subentry_id=subentry.subentry_id,
            )


class StockNumber(PetCareEntity, NumberEntity):
    """How much is left. Counts down per dose; set it when restocking."""

    _attr_icon = "mdi:package-variant"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 100000
    _attr_native_step = 0.5

    def __init__(self, entry, subentry, key) -> None:
        super().__init__(entry, subentry, key)
        self._attr_native_unit_of_measurement = subentry.data.get(CONF_UNIT) or None

    @property
    def native_value(self) -> float | None:
        return self.status.stock

    async def async_set_native_value(self, value: float) -> None:
        await self._data.async_set_stock(self._subentry, value)


class LogValueNumber(PetCareEntity, NumberEntity):
    """Type a value here to log a new measurement."""

    _attr_icon = "mdi:pencil-plus"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_step = 0.1

    def __init__(self, entry, subentry, key) -> None:
        super().__init__(entry, subentry, key)
        self._attr_native_unit_of_measurement = subentry.data.get(CONF_UNIT) or None

    @property
    def native_value(self) -> float | None:
        return self.status.last_value

    async def async_set_native_value(self, value: float) -> None:
        await self._data.async_log_measurement(self._subentry, value, self._context)
