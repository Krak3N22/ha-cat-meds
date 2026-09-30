"""Tests for entities and actions: doses, stock, double doses, undo, measurements."""

from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pet_care.const import DOMAIN

from .conftest import DOSE_ID, MEASUREMENT_ID, entity_id


async def press(hass: HomeAssistant, entity: str, context: Context | None = None) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity}, blocking=True, context=context
    )


def state(hass: HomeAssistant, entity: str) -> str:
    return hass.states.get(entity).state


async def test_entities_created(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """A medication and a measurement get their entities."""
    assert setup_entry.state is ConfigEntryState.LOADED
    assert state(hass, entity_id(hass, "number", DOSE_ID, "stock")) == "200.0"
    assert state(hass, entity_id(hass, "sensor", DOSE_ID, "last_given")) == STATE_UNKNOWN
    assert hass.states.get(entity_id(hass, "sensor", DOSE_ID, "next_due"))
    assert hass.states.get(entity_id(hass, "binary_sensor", DOSE_ID, "overdue"))
    assert hass.states.get(entity_id(hass, "button", DOSE_ID, "undo"))
    # Never measured, so the weekly measurement is due right away.
    assert state(hass, entity_id(hass, "binary_sensor", MEASUREMENT_ID, "overdue")) == STATE_ON
    assert hass.states.get(entity_id(hass, "number", MEASUREMENT_ID, "log_value"))


async def test_give_dose(hass: HomeAssistant, setup_entry: MockConfigEntry, hass_admin_user) -> None:
    """Giving a dose logs who gave it and counts down stock."""
    await press(
        hass,
        entity_id(hass, "button", DOSE_ID, "give_dose"),
        Context(user_id=hass_admin_user.id),
    )
    assert state(hass, entity_id(hass, "number", DOSE_ID, "stock")) == "199.0"
    assert state(hass, entity_id(hass, "sensor", DOSE_ID, "last_given_by")) == hass_admin_user.name
    assert state(hass, entity_id(hass, "sensor", DOSE_ID, "last_given")) != STATE_UNKNOWN


async def test_double_dose_needs_confirmation(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """A second dose soon after is refused, unless pressed again to confirm."""
    button = entity_id(hass, "button", DOSE_ID, "give_dose")
    stock = entity_id(hass, "number", DOSE_ID, "stock")
    await press(hass, button)

    with pytest.raises(ServiceValidationError) as err:
        await press(hass, button)
    assert err.value.translation_key == "already_given"
    assert state(hass, stock) == "199.0"

    await press(hass, button)
    assert state(hass, stock) == "198.0"


async def test_force_skips_double_dose_warning(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """The give_dose action can skip the warning."""
    button = entity_id(hass, "button", DOSE_ID, "give_dose")
    await press(hass, button)
    await hass.services.async_call(
        DOMAIN, "give_dose", {"entity_id": button, "force": True}, blocking=True
    )
    assert state(hass, entity_id(hass, "number", DOSE_ID, "stock")) == "198.0"


async def test_backdated_dose(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """A dose can be logged at an earlier time."""
    button = entity_id(hass, "button", DOSE_ID, "give_dose")
    last_given = entity_id(hass, "sensor", DOSE_ID, "last_given")
    earlier = dt_util.utcnow().replace(microsecond=0) - timedelta(hours=3)

    await hass.services.async_call(
        DOMAIN, "give_dose", {"entity_id": button, "given_at": earlier}, blocking=True
    )
    assert dt_util.parse_datetime(state(hass, last_given)) == earlier

    # Three hours apart is outside the 2 hour double dose window.
    await press(hass, button)
    assert dt_util.parse_datetime(state(hass, last_given)) > earlier

    # A backdated dose close to another one also needs confirmation.
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "give_dose",
            {"entity_id": button, "given_at": earlier + timedelta(minutes=30)},
            blocking=True,
        )


async def test_dose_in_future_refused(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """A dose can't be logged in the future."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "give_dose",
            {
                "entity_id": entity_id(hass, "button", DOSE_ID, "give_dose"),
                "given_at": dt_util.utcnow() + timedelta(hours=1),
            },
            blocking=True,
        )
    assert err.value.translation_key == "in_future"


async def test_undo_dose(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Undo removes the latest dose and gives back the stock."""
    undo = entity_id(hass, "button", DOSE_ID, "undo")
    with pytest.raises(ServiceValidationError) as err:
        await press(hass, undo)
    assert err.value.translation_key == "nothing_to_undo"

    await press(hass, entity_id(hass, "button", DOSE_ID, "give_dose"))
    await press(hass, undo)
    assert state(hass, entity_id(hass, "number", DOSE_ID, "stock")) == "200.0"
    assert state(hass, entity_id(hass, "sensor", DOSE_ID, "last_given")) == STATE_UNKNOWN


async def test_undo_removes_latest_logged_not_latest_time(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Undo removes what was logged last, even if it was backdated."""
    button = entity_id(hass, "button", DOSE_ID, "give_dose")
    last_given = entity_id(hass, "sensor", DOSE_ID, "last_given")
    await press(hass, button)
    now_state = state(hass, last_given)

    await hass.services.async_call(
        DOMAIN,
        "give_dose",
        {"entity_id": button, "given_at": dt_util.utcnow() - timedelta(hours=5)},
        blocking=True,
    )
    await hass.services.async_call(DOMAIN, "undo", {"entity_id": button}, blocking=True)
    assert state(hass, last_given) == now_state
    assert state(hass, entity_id(hass, "number", DOSE_ID, "stock")) == "199.0"


async def test_set_stock(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Stock can be set when opening a new inhaler."""
    stock = entity_id(hass, "number", DOSE_ID, "stock")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": stock, "value": 120}, blocking=True
    )
    assert state(hass, stock) == "120.0"


async def test_measurement(hass: HomeAssistant, setup_entry: MockConfigEntry, hass_admin_user) -> None:
    """Logging a value updates the sensors and clears overdue; undo reverts it."""
    log_value = entity_id(hass, "number", MEASUREMENT_ID, "log_value")
    value = entity_id(hass, "sensor", MEASUREMENT_ID, "value")
    overdue = entity_id(hass, "binary_sensor", MEASUREMENT_ID, "overdue")

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": log_value, "value": 6.5},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    assert state(hass, value) == "6.5"
    assert hass.states.get(value).attributes["unit_of_measurement"] == "mmol/L"
    assert state(hass, overdue) == STATE_OFF
    assert (
        state(hass, entity_id(hass, "sensor", MEASUREMENT_ID, "last_measured_by"))
        == hass_admin_user.name
    )

    await press(hass, entity_id(hass, "button", MEASUREMENT_ID, "undo"))
    assert state(hass, value) == STATE_UNKNOWN
    assert state(hass, overdue) == STATE_ON


async def test_backdated_measurement(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """A measurement can be logged at an earlier time."""
    earlier = dt_util.utcnow().replace(microsecond=0) - timedelta(days=1)
    await hass.services.async_call(
        DOMAIN,
        "log_measurement",
        {
            "entity_id": entity_id(hass, "number", MEASUREMENT_ID, "log_value"),
            "value": 5.2,
            "measured_at": earlier,
        },
        blocking=True,
    )
    assert state(hass, entity_id(hass, "sensor", MEASUREMENT_ID, "value")) == "5.2"
    assert (
        dt_util.parse_datetime(
            state(hass, entity_id(hass, "sensor", MEASUREMENT_ID, "last_measured"))
        )
        == earlier
    )


async def test_action_on_wrong_entity(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Actions refuse entities of the wrong kind."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "log_measurement",
            {"entity_id": entity_id(hass, "button", DOSE_ID, "give_dose"), "value": 1},
            blocking=True,
        )
    assert err.value.translation_key == "not_measurement"

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "undo", {"entity_id": "sun.sun"}, blocking=True
        )
    assert err.value.translation_key == "not_pet_care_entity"


async def test_data_survives_reload(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Doses and stock are stored."""
    await press(hass, entity_id(hass, "button", DOSE_ID, "give_dose"))
    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, entity_id(hass, "number", DOSE_ID, "stock")) == "199.0"
    assert state(hass, entity_id(hass, "sensor", DOSE_ID, "last_given")) != STATE_UNKNOWN


async def test_unload(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """The pet can be unloaded."""
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    assert setup_entry.state is ConfigEntryState.NOT_LOADED
