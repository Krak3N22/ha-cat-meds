"""Actions for logging with a custom time, and undoing."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN, SUBENTRY_DOSE, SUBENTRY_MEASUREMENT
from .data import PetCareData

ATTR_GIVEN_AT = "given_at"
ATTR_MEASURED_AT = "measured_at"
ATTR_FORCE = "force"
ATTR_VALUE = "value"
ATTR_USER_ID = "user_id"

SERVICE_GIVE_DOSE = "give_dose"
SERVICE_LOG_MEASUREMENT = "log_measurement"
SERVICE_UNDO = "undo"
SERVICE_REFILL = "refill"
SERVICE_SKIP = "skip"
ATTR_AMOUNT = "amount"

_TARGET = {vol.Required(ATTR_ENTITY_ID): cv.entity_ids}
# Who did it, e.g. the user who tapped a notification. Defaults to the caller.
_USER = {vol.Optional(ATTR_USER_ID): vol.Any(None, cv.string)}

GIVE_DOSE_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Optional(ATTR_GIVEN_AT): cv.datetime,
        vol.Optional(ATTR_FORCE, default=False): cv.boolean,
        **_USER,
    }
)
LOG_MEASUREMENT_SCHEMA = vol.Schema(
    {
        **_TARGET,
        vol.Required(ATTR_VALUE): vol.Coerce(float),
        vol.Optional(ATTR_MEASURED_AT): cv.datetime,
        **_USER,
    }
)
UNDO_SCHEMA = vol.Schema(_TARGET)
SKIP_SCHEMA = vol.Schema({**_TARGET, **_USER})
REFILL_SCHEMA = vol.Schema(
    {**_TARGET, vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(float), vol.Range(min=0))}
)


def _resolve(
    hass: HomeAssistant, entity_id: str, subentry_type: str | None
) -> tuple[PetCareData, ConfigSubentry]:
    """Find the item that a Pet Care entity belongs to."""
    entity = er.async_get(hass).async_get(entity_id)
    entry = (
        hass.config_entries.async_get_entry(entity.config_entry_id)
        if entity and entity.config_entry_id
        else None
    )
    if (
        entity is None
        or entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
        or entity.config_subentry_id not in entry.subentries
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_pet_care_entity",
            translation_placeholders={"entity_id": entity_id},
        )
    subentry = entry.subentries[entity.config_subentry_id]
    if subentry_type is not None and subentry.subentry_type != subentry_type:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=f"not_{subentry_type}",
            translation_placeholders={"entity_id": entity_id},
        )
    return entry.runtime_data, subentry


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Pet Care actions."""

    async def give_dose(call: ServiceCall) -> None:
        for entity_id in call.data[ATTR_ENTITY_ID]:
            data, subentry = _resolve(hass, entity_id, SUBENTRY_DOSE)
            await data.async_give_dose(
                subentry,
                call.context,
                call.data.get(ATTR_GIVEN_AT),
                call.data[ATTR_FORCE],
                call.data.get(ATTR_USER_ID) or None,
            )

    async def log_measurement(call: ServiceCall) -> None:
        for entity_id in call.data[ATTR_ENTITY_ID]:
            data, subentry = _resolve(hass, entity_id, SUBENTRY_MEASUREMENT)
            await data.async_log_measurement(
                subentry,
                call.data[ATTR_VALUE],
                call.context,
                call.data.get(ATTR_MEASURED_AT),
                call.data.get(ATTR_USER_ID) or None,
            )

    async def undo(call: ServiceCall) -> None:
        for entity_id in call.data[ATTR_ENTITY_ID]:
            data, subentry = _resolve(hass, entity_id, None)
            await data.async_undo(subentry, call.context)

    hass.services.async_register(DOMAIN, SERVICE_GIVE_DOSE, give_dose, GIVE_DOSE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_LOG_MEASUREMENT, log_measurement, LOG_MEASUREMENT_SCHEMA
    )
    async def refill(call: ServiceCall) -> None:
        for entity_id in call.data[ATTR_ENTITY_ID]:
            data, subentry = _resolve(hass, entity_id, SUBENTRY_DOSE)
            await data.async_refill(subentry, call.data.get(ATTR_AMOUNT), call.context)

    async def skip(call: ServiceCall) -> None:
        for entity_id in call.data[ATTR_ENTITY_ID]:
            data, subentry = _resolve(hass, entity_id, None)
            await data.async_skip(subentry, call.context, call.data.get(ATTR_USER_ID) or None)

    hass.services.async_register(DOMAIN, SERVICE_UNDO, undo, UNDO_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SKIP, skip, SKIP_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REFILL, refill, REFILL_SCHEMA)
