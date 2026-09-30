"""End-to-end test of the dose reminder blueprint."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import shutil

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from .conftest import DOSE_ID, entity_id

BLUEPRINT = Path(__file__).parents[1] / "blueprints/automation/pet_care/dose_reminder.yaml"


@pytest.fixture
async def reminder(
    hass: HomeAssistant, setup_entry: MockConfigEntry, tmp_path: Path
) -> list[ServiceCall]:
    """Set up the blueprint for the inhaler with one phone; return notify calls."""
    hass.config.config_dir = str(tmp_path)
    target = tmp_path / "blueprints/automation/pet_care/dose_reminder.yaml"
    target.parent.mkdir(parents=True)
    shutil.copy(BLUEPRINT, target)

    phone_entry = MockConfigEntry(domain="mobile_app")
    phone_entry.add_to_hass(hass)
    phone = dr.async_get(hass).async_get_or_create(
        config_entry_id=phone_entry.entry_id,
        identifiers={("mobile_app", "phone")},
        name="Test Phone",
    )
    calls = async_mock_service(hass, "notify", "mobile_app_test_phone")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "pet_care/dose_reminder.yaml",
                    "input": {
                        "overdue_sensor": entity_id(hass, "binary_sensor", DOSE_ID, "overdue"),
                        "give_dose_button": entity_id(hass, "button", DOSE_ID, "give_dose"),
                        "notify_devices": [phone.id],
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return calls


async def _make_overdue(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    next_due = dt_util.parse_datetime(
        hass.states.get(entity_id(hass, "sensor", DOSE_ID, "next_due")).state
    )
    freezer.move_to(next_due + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, "binary_sensor", DOSE_ID, "overdue")).state == STATE_ON


async def test_given_from_notification(
    hass: HomeAssistant,
    reminder: list[ServiceCall],
    freezer: FrozenDateTimeFactory,
    hass_admin_user,
) -> None:
    """Overdue sends a notification; "Given" logs the dose as whoever tapped it."""
    button = entity_id(hass, "button", DOSE_ID, "give_dose")
    await _make_overdue(hass, freezer)

    assert len(reminder) == 1
    sent = reminder[0].data
    assert sent["title"] == "Freja Inhaler"
    assert sent["data"]["tag"] == f"pet_care_{button}"
    assert [a["title"] for a in sent["data"]["actions"]] == ["Given", "Snooze", "Skip"]

    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": f"PET_CARE_GIVEN_{button}"},
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get(entity_id(hass, "sensor", DOSE_ID, "last_given_by")).state
        == hass_admin_user.name
    )
    assert hass.states.get(entity_id(hass, "binary_sensor", DOSE_ID, "overdue")).state == STATE_OFF
    assert reminder[-1].data["message"] == "clear_notification"
    assert reminder[-1].data["data"]["tag"] == f"pet_care_{button}"


async def test_skip_from_notification(
    hass: HomeAssistant, reminder: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    """"Skip" skips the dose without logging it as given."""
    button = entity_id(hass, "button", DOSE_ID, "give_dose")
    await _make_overdue(hass, freezer)

    hass.bus.async_fire("mobile_app_notification_action", {"action": f"PET_CARE_SKIP_{button}"})
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(hass, "binary_sensor", DOSE_ID, "overdue")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "sensor", DOSE_ID, "last_given")).state == STATE_UNKNOWN
    assert hass.states.get(entity_id(hass, "number", DOSE_ID, "stock")).state == "200.0"
    assert reminder[-1].data["message"] == "clear_notification"


async def test_reminds_again_without_answer(
    hass: HomeAssistant, reminder: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    """Without an answer it reminds again after the repeat time."""
    await _make_overdue(hass, freezer)
    assert len(reminder) == 1

    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(reminder) == 2
    assert reminder[1].data["message"] == "Time for the next dose."
