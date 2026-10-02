"""End-to-end tests of the dose reminder blueprint."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
import shutil

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigSubentryData
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

from custom_components.pet_care.const import (
    CONF_DOSE_AMOUNT,
    CONF_INTERVAL_DAYS,
    CONF_TIMES,
    DOMAIN,
    SUBENTRY_DOSE,
)

from .conftest import DOSE_ID, entity_id

BLUEPRINT = Path(__file__).parents[1] / "blueprints/automation/pet_care/dose_reminder.yaml"
TABLETS_ID = "tablets"


def _given(sensor: str) -> str:
    return f"PET_CARE_GIVEN_{sensor}"


async def _until(check: Callable[[], bool]) -> None:
    """Let the event loop run until check() is true.

    Reminders wait for the dose, so hass.async_block_till_done() would wait for
    them forever. Time is frozen, so only yield instead of sleeping.
    """
    for _ in range(2000):
        if check():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition not met")


@pytest.fixture
async def setup(
    hass: HomeAssistant, setup_entry: MockConfigEntry, tmp_path: Path
) -> dict:
    """Freja's inhaler and Phoenix's tablets in one reminder, with one phone."""
    phoenix = MockConfigEntry(
        domain=DOMAIN,
        title="Phoenix",
        data={},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_DOSE_AMOUNT: 1, CONF_TIMES: ["20:00"], CONF_INTERVAL_DAYS: 0},
                subentry_id=TABLETS_ID,
                subentry_type=SUBENTRY_DOSE,
                title="Tablets",
                unique_id=None,
            )
        ],
    )
    phoenix.add_to_hass(hass)
    assert await hass.config_entries.async_setup(phoenix.entry_id)

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

    inhaler = entity_id(hass, "binary_sensor", DOSE_ID, "overdue")
    tablets = entity_id(hass, "binary_sensor", TABLETS_ID, "overdue")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "pet_care/dose_reminder.yaml",
                    "input": {
                        "overdue_sensors": [inhaler, tablets],
                        "notify_devices": [phone.id],
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return {"calls": calls, "inhaler": inhaler, "tablets": tablets}


def _sent(calls: list[ServiceCall], sensor: str) -> list[dict]:
    """Notifications (not clears) sent for one medication."""
    return [
        c.data
        for c in calls
        if c.data["data"]["tag"] == f"pet_care_{sensor}"
        and c.data["message"] != "clear_notification"
    ]


def _cleared(calls: list[ServiceCall], sensor: str) -> bool:
    return any(
        c.data["message"] == "clear_notification"
        and c.data["data"]["tag"] == f"pet_care_{sensor}"
        for c in calls
    )


async def _make_overdue(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup: dict) -> None:
    """Move past 20:00, when both medications are due."""
    next_due = dt_util.parse_datetime(
        hass.states.get(entity_id(hass, "sensor", DOSE_ID, "next_due")).state
    )
    freezer.move_to(next_due + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await _until(
        lambda: hass.states.get(setup["inhaler"]).state == STATE_ON
        and hass.states.get(setup["tablets"]).state == STATE_ON
    )
    # The trigger waits "for" 0 minutes before it fires.
    async_fire_time_changed(hass)
    calls = setup["calls"]
    await _until(
        lambda: len(_sent(calls, setup["inhaler"])) == 1
        and len(_sent(calls, setup["tablets"])) == 1
    )


async def test_one_notification_per_medication(
    hass: HomeAssistant, setup: dict, freezer: FrozenDateTimeFactory
) -> None:
    """Each overdue medication gets its own notification and buttons."""
    await _make_overdue(hass, freezer, setup)
    calls = setup["calls"]

    inhaler = _sent(calls, setup["inhaler"])[0]
    assert inhaler["title"] == "Freja Inhaler"
    assert [a["action"] for a in inhaler["data"]["actions"]] == [
        f"PET_CARE_GIVEN_{setup['inhaler']}",
        f"PET_CARE_SNOOZE_{setup['inhaler']}",
        f"PET_CARE_SKIP_{setup['inhaler']}",
    ]
    assert [a["title"] for a in inhaler["data"]["actions"]] == ["Given", "Snooze", "Skip"]
    assert _sent(calls, setup["tablets"])[0]["title"] == "Phoenix Tablets"


async def test_given_only_affects_that_medication(
    hass: HomeAssistant, setup: dict, freezer: FrozenDateTimeFactory, hass_admin_user
) -> None:
    """"Given" logs the dose as whoever tapped it and clears only that notification."""
    await _make_overdue(hass, freezer, setup)
    calls = setup["calls"]

    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": _given(setup["inhaler"])},
        context=Context(user_id=hass_admin_user.id),
    )
    await _until(lambda: _cleared(calls, setup["inhaler"]))

    assert (
        hass.states.get(entity_id(hass, "sensor", DOSE_ID, "last_given_by")).state
        == hass_admin_user.name
    )
    assert hass.states.get(setup["inhaler"]).state == STATE_OFF
    assert hass.states.get(setup["tablets"]).state == STATE_ON
    assert not _cleared(calls, setup["tablets"])


async def test_skip_from_notification(
    hass: HomeAssistant, setup: dict, freezer: FrozenDateTimeFactory
) -> None:
    """"Skip" skips the dose without logging it as given."""
    await _make_overdue(hass, freezer, setup)
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"PET_CARE_SKIP_{setup['inhaler']}"}
    )
    await _until(lambda: _cleared(setup["calls"], setup["inhaler"]))

    assert hass.states.get(setup["inhaler"]).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "sensor", DOSE_ID, "last_given")).state == STATE_UNKNOWN
    assert hass.states.get(entity_id(hass, "number", DOSE_ID, "stock")).state == "200.0"


async def test_snooze_clears_until_next_reminder(
    hass: HomeAssistant, setup: dict, freezer: FrozenDateTimeFactory
) -> None:
    """"Snooze" hides the notification; it comes back at the next reminder."""
    await _make_overdue(hass, freezer, setup)
    calls = setup["calls"]
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"PET_CARE_SNOOZE_{setup['inhaler']}"}
    )
    await _until(lambda: _cleared(calls, setup["inhaler"]))
    assert hass.states.get(setup["inhaler"]).state == STATE_ON

    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await _until(lambda: len(_sent(calls, setup["inhaler"])) == 2)


async def test_reminds_again_without_answer(
    hass: HomeAssistant, setup: dict, freezer: FrozenDateTimeFactory
) -> None:
    """Without an answer it reminds again after the repeat time."""
    await _make_overdue(hass, freezer, setup)
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await _until(lambda: len(_sent(setup["calls"], setup["tablets"])) == 2)
    assert _sent(setup["calls"], setup["tablets"])[1]["message"] == "Time for the next dose."


async def test_other_notifications_are_ignored(
    hass: HomeAssistant, setup: dict, freezer: FrozenDateTimeFactory
) -> None:
    """Answers for other automations or unknown sensors do nothing."""
    await _make_overdue(hass, freezer, setup)
    hass.bus.async_fire("mobile_app_notification_action", {"action": "SOMETHING_ELSE"})
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": _given("binary_sensor.not_ours")}
    )
    for _ in range(200):
        await asyncio.sleep(0)
    assert hass.states.get(setup["inhaler"]).state == STATE_ON
    assert hass.states.get(setup["tablets"]).state == STATE_ON


async def test_resumes_after_restart(
    hass: HomeAssistant, setup: dict, freezer: FrozenDateTimeFactory
) -> None:
    """After a restart the blueprint fires a resume event per overdue medication,
    which starts reminding again."""
    await _make_overdue(hass, freezer, setup)
    hass.bus.async_fire("pet_care_reminder_resume", {"entity_id": setup["inhaler"]})
    await _until(lambda: len(_sent(setup["calls"], setup["inhaler"])) == 2)
    assert len(_sent(setup["calls"], setup["tablets"])) == 1
