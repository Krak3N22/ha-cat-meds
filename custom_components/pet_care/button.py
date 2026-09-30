"""Buttons: log a given dose, and undo the latest entry."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PetCareConfigEntry
from .const import SUBENTRY_DOSE
from .entity import PetCareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PetCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    for subentry in entry.subentries.values():
        entities: list[ButtonEntity] = [UndoButton(entry, subentry, "undo")]
        if subentry.subentry_type == SUBENTRY_DOSE:
            entities.append(GiveDoseButton(entry, subentry, "give_dose"))
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)


class GiveDoseButton(PetCareEntity, ButtonEntity):
    """Press when a dose has been given."""

    _attr_icon = "mdi:medication"

    async def async_press(self) -> None:
        """Log the dose, attributed to the user who pressed."""
        await self._data.async_give_dose(self._subentry, self._context)


class UndoButton(PetCareEntity, ButtonEntity):
    """Undo the latest logged dose or measurement, e.g. after a mis-tap."""

    _attr_icon = "mdi:undo"
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Remove the latest entry."""
        await self._data.async_undo(self._subentry, self._context)
