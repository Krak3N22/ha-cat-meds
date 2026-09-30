"""Tests for adding pets, medications and measurements in the UI."""

from __future__ import annotations

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pet_care.const import (
    CONF_DOSE_AMOUNT,
    CONF_GUARD_HOURS,
    CONF_INTERVAL_DAYS,
    CONF_STOCK,
    CONF_TIMES,
    CONF_TRACK_STOCK,
    CONF_UNIT,
    DOMAIN,
    SUBENTRY_DOSE,
    SUBENTRY_MEASUREMENT,
)

from .conftest import DOSE_ID, entity_id

DOSE_INPUT = {
    CONF_NAME: "Tablets",
    CONF_DOSE_AMOUNT: 0.5,
    CONF_UNIT: "tablets",
    CONF_TIMES: "20:00, 8:00",
    CONF_INTERVAL_DAYS: 0,
    CONF_GUARD_HOURS: 2,
    CONF_TRACK_STOCK: True,
    CONF_STOCK: 30,
}


async def test_add_pet(hass: HomeAssistant) -> None:
    """A pet is added with just a name."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Phoenix"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Phoenix"


async def test_add_medication(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """A medication is added and gets its entities."""
    result = await hass.config_entries.subentries.async_init(
        (setup_entry.entry_id, SUBENTRY_DOSE), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], DOSE_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentry = next(s for s in setup_entry.subentries.values() if s.title == "Tablets")
    assert subentry.data[CONF_TIMES] == ["08:00", "20:00"]
    assert CONF_NAME not in subentry.data
    stock = entity_id(hass, "number", subentry.subentry_id, "stock")
    assert hass.states.get(stock).state == "30.0"
    # 30 tablets, half a tablet twice a day.
    days_left = entity_id(hass, "sensor", subentry.subentry_id, "days_left")
    assert hass.states.get(days_left).state == "30.0"

    # No pack size: no refill button, and refill needs an amount.
    assert not er.async_get(hass).async_get_entity_id(
        "button", DOMAIN, f"{subentry.subentry_id}_refill"
    )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, "refill", {"entity_id": stock}, blocking=True)
    assert err.value.translation_key == "no_pack_size"


async def test_add_medication_without_schedule(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """An as-needed medication has no due time, overdue or skip."""
    result = await hass.config_entries.subentries.async_init(
        (setup_entry.entry_id, SUBENTRY_DOSE), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**DOSE_INPUT, CONF_NAME: "As needed", CONF_TIMES: ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentry = next(s for s in setup_entry.subentries.values() if s.title == "As needed")
    registry = er.async_get(hass)
    for platform, key in (("binary_sensor", "overdue"), ("sensor", "next_due"), ("button", "skip")):
        assert not registry.async_get_entity_id(platform, DOMAIN, f"{subentry.subentry_id}_{key}")

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "skip",
            {"entity_id": entity_id(hass, "button", subentry.subentry_id, "give_dose")},
            blocking=True,
        )
    assert err.value.translation_key == "no_schedule"


async def test_add_medication_invalid_times(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Badly written times are rejected with an error on the field."""
    result = await hass.config_entries.subentries.async_init(
        (setup_entry.entry_id, SUBENTRY_DOSE), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**DOSE_INPUT, CONF_TIMES: "8 in the morning"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TIMES: "invalid_times"}


async def test_add_measurement(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """A measurement is added."""
    result = await hass.config_entries.subentries.async_init(
        (setup_entry.entry_id, SUBENTRY_MEASUREMENT), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_NAME: "Weight", CONF_UNIT: "kg", CONF_TIMES: "", CONF_INTERVAL_DAYS: 30},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(s for s in setup_entry.subentries.values() if s.title == "Weight")
    assert subentry.data[CONF_TIMES] == []
    assert subentry.data[CONF_INTERVAL_DAYS] == 30


async def test_reconfigure_medication_keeps_history(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Editing a medication keeps its stock and history."""
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, "button", DOSE_ID, "give_dose")},
        blocking=True,
    )
    result = await setup_entry.start_subentry_reconfigure_flow(hass, DOSE_ID)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Asthma inhaler",
            CONF_DOSE_AMOUNT: 2,
            CONF_UNIT: "puffs",
            CONF_TIMES: "08:00, 20:00",
            CONF_INTERVAL_DAYS: 0,
            CONF_GUARD_HOURS: 2,
            CONF_TRACK_STOCK: True,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    subentry = setup_entry.subentries[DOSE_ID]
    assert subentry.title == "Asthma inhaler"
    assert subentry.data[CONF_DOSE_AMOUNT] == 2
    assert hass.states.get(entity_id(hass, "number", DOSE_ID, "stock")).state == "199.0"
