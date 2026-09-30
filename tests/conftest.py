"""Shared fixtures: a pet with one medication and one measurement."""

from __future__ import annotations

import pytest

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
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

DOSE_ID = "inhaler"
MEASUREMENT_ID = "glucose"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/pet_care."""
    return


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """A pet called Freja with an inhaler and weekly glucose."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Freja",
        data={},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_DOSE_AMOUNT: 1,
                    CONF_UNIT: "puffs",
                    CONF_TIMES: ["20:00"],
                    CONF_INTERVAL_DAYS: 0,
                    CONF_TRACK_STOCK: True,
                    CONF_STOCK: 200,
                    CONF_GUARD_HOURS: 2,
                },
                subentry_id=DOSE_ID,
                subentry_type=SUBENTRY_DOSE,
                title="Inhaler",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={CONF_UNIT: "mmol/L", CONF_TIMES: [], CONF_INTERVAL_DAYS: 7},
                subentry_id=MEASUREMENT_ID,
                subentry_type=SUBENTRY_MEASUREMENT,
                title="Glucose",
                unique_id=None,
            ),
        ],
    )


@pytest.fixture
async def setup_entry(hass: HomeAssistant, mock_entry: MockConfigEntry) -> MockConfigEntry:
    """Set up the pet."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry


def entity_id(hass: HomeAssistant, platform: str, subentry_id: str, key: str) -> str:
    """Look up an entity id from its unique id."""
    found = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{subentry_id}_{key}"
    )
    assert found, f"{platform} {subentry_id}_{key} not found"
    return found
