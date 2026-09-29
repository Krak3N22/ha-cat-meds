"""Button to log a given dose."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CatMedsConfigEntry
from .const import SUBENTRY_DOSE
from .entity import CatMedsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CatMedsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == SUBENTRY_DOSE:
            async_add_entities(
                [GiveDoseButton(entry, subentry, "give_dose")],
                config_subentry_id=subentry.subentry_id,
            )


class GiveDoseButton(CatMedsEntity, ButtonEntity):
    """Press when a dose has been given."""

    _attr_icon = "mdi:medication"

    async def async_press(self) -> None:
        """Log the dose, attributed to the user who pressed."""
        await self._data.async_give_dose(self._subentry, self._context)
