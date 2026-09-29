"""Config flow: one entry per cat, one subentry per medication/measurement."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from . import schedule
from .const import (
    CONF_DOSE_AMOUNT,
    CONF_INTERVAL_DAYS,
    CONF_STOCK,
    CONF_TIMES,
    CONF_TRACK_STOCK,
    CONF_UNIT,
    DOMAIN,
    SUBENTRY_DOSE,
    SUBENTRY_MEASUREMENT,
)


def _number(minimum: float, maximum: float, step: float) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=step, mode=NumberSelectorMode.BOX
        )
    )


class CatMedsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a cat."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data={})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_NAME): TextSelector()}),
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {
            SUBENTRY_DOSE: DoseSubentryFlow,
            SUBENTRY_MEASUREMENT: MeasurementSubentryFlow,
        }


class _ItemSubentryFlow(ConfigSubentryFlow):
    """Shared add/edit logic for tracked items."""

    defaults: dict[str, Any] = {}

    def _schema(self, reconfigure: bool) -> vol.Schema:
        raise NotImplementedError

    def _parse(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        data = dict(user_input)
        try:
            data[CONF_TIMES] = schedule.parse_times(user_input.get(CONF_TIMES, ""))
        except ValueError:
            return data, {CONF_TIMES: "invalid_times"}
        return data, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._parse(user_input)
            if not errors:
                return self.async_create_entry(title=data.pop(CONF_NAME), data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                self._schema(reconfigure=False), user_input or self.defaults
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._parse(user_input)
            if not errors:
                title = data.pop(CONF_NAME)
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=title,
                    data={**subentry.data, **data},
                )
        current = {
            **subentry.data,
            CONF_NAME: subentry.title,
            CONF_TIMES: ", ".join(subentry.data.get(CONF_TIMES, [])),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                self._schema(reconfigure=True), user_input or current
            ),
            errors=errors,
        )


class DoseSubentryFlow(_ItemSubentryFlow):
    """Add or edit a medication, e.g. an inhaler."""

    defaults = {
        CONF_DOSE_AMOUNT: 1,
        CONF_UNIT: "doser",
        CONF_TIMES: "08:00, 20:00",
        CONF_TRACK_STOCK: True,
        CONF_STOCK: 0,
    }

    def _schema(self, reconfigure: bool) -> vol.Schema:
        schema = {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Required(CONF_DOSE_AMOUNT): _number(0.5, 1000, 0.5),
            vol.Optional(CONF_UNIT, default=""): TextSelector(),
            vol.Optional(CONF_TIMES, default=""): TextSelector(),
            vol.Optional(CONF_INTERVAL_DAYS, default=0): _number(0, 365, 1),
            vol.Optional(CONF_TRACK_STOCK, default=False): BooleanSelector(),
        }
        if not reconfigure:
            # After creation, stock is changed with the stock entity instead.
            schema[vol.Optional(CONF_STOCK, default=0)] = _number(0, 100000, 0.5)
        return vol.Schema(schema)


class MeasurementSubentryFlow(_ItemSubentryFlow):
    """Add or edit a measurement, e.g. blood glucose."""

    defaults = {CONF_UNIT: "mmol/L", CONF_INTERVAL_DAYS: 7}

    def _schema(self, reconfigure: bool) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Optional(CONF_UNIT, default=""): TextSelector(),
                vol.Optional(CONF_TIMES, default=""): TextSelector(),
                vol.Optional(CONF_INTERVAL_DAYS, default=0): _number(0, 365, 1),
            }
        )
