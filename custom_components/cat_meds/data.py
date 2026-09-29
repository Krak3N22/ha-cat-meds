"""Persistent data for one cat: event log and stock per tracked item."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import schedule
from .const import (
    CONF_DOSE_AMOUNT,
    CONF_INTERVAL_DAYS,
    CONF_STOCK,
    CONF_TIMES,
    CONF_TRACK_STOCK,
    CONF_UNIT,
    DOMAIN,
    EVENT_DOSE_GIVEN,
    EVENT_MEASUREMENT_LOGGED,
    MAX_EVENTS,
    signal_update,
)

STORAGE_VERSION = 1


def storage_key(entry_id: str) -> str:
    """Return the storage key for a config entry."""
    return f"{DOMAIN}.{entry_id}"


@dataclass
class ItemStatus:
    """Current state of a tracked item."""

    last: datetime | None
    last_by: str | None
    last_value: float | None
    next_due: datetime | None
    overdue: bool
    stock: float | None


class CatMedsData:
    """Event log and stock for all items of one cat (config entry)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._items: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        """Load stored data and sync it with the entry's subentries."""
        stored = await self._store.async_load() or {}
        self._items = stored.get("items", {})
        for subentry_id in list(self._items):
            if subentry_id not in self.entry.subentries:
                del self._items[subentry_id]
        for subentry in self.entry.subentries.values():
            item = self._item(subentry.subentry_id)
            if subentry.data.get(CONF_TRACK_STOCK) and "stock" not in item:
                item["stock"] = float(subentry.data.get(CONF_STOCK, 0))
        await self._async_save()

    def _item(self, subentry_id: str) -> dict[str, Any]:
        return self._items.setdefault(
            subentry_id, {"created": dt_util.utcnow().isoformat(), "events": []}
        )

    async def _async_save(self) -> None:
        await self._store.async_save({"items": self._items})

    @callback
    def async_notify(self) -> None:
        """Tell entities to refresh."""
        async_dispatcher_send(self.hass, signal_update(self.entry.entry_id))

    def status(self, subentry: ConfigSubentry) -> ItemStatus:
        """Compute the current status of an item."""
        item = self._item(subentry.subentry_id)
        events = item["events"]
        last_event = events[-1] if events else None
        last = dt_util.parse_datetime(last_event["ts"]) if last_event else None
        now = dt_util.now()
        due = schedule.next_due(
            now,
            last,
            dt_util.parse_datetime(item["created"]),
            subentry.data.get(CONF_TIMES, []),
            subentry.data.get(CONF_INTERVAL_DAYS) or 0,
        )
        return ItemStatus(
            last=last,
            last_by=last_event.get("user") if last_event else None,
            last_value=last_event.get("value") if last_event else None,
            next_due=due,
            overdue=schedule.is_overdue(now, due),
            stock=item.get("stock") if subentry.data.get(CONF_TRACK_STOCK) else None,
        )

    async def _async_log(
        self, subentry: ConfigSubentry, context: Context | None, value: float | None
    ) -> dict[str, Any]:
        user_id = context.user_id if context else None
        user = await self.hass.auth.async_get_user(user_id) if user_id else None
        event = {
            "ts": dt_util.utcnow().isoformat(),
            "user_id": user_id,
            "user": user.name if user else None,
        }
        if value is not None:
            event["value"] = value
        events = self._item(subentry.subentry_id)["events"]
        events.append(event)
        del events[:-MAX_EVENTS]
        return event

    async def async_give_dose(
        self, subentry: ConfigSubentry, context: Context | None
    ) -> None:
        """Log a dose and take it out of stock."""
        event = await self._async_log(subentry, context, None)
        item = self._item(subentry.subentry_id)
        if subentry.data.get(CONF_TRACK_STOCK):
            amount = float(subentry.data.get(CONF_DOSE_AMOUNT, 1))
            item["stock"] = max(0.0, item.get("stock", 0.0) - amount)
        await self._async_save()
        self.hass.bus.async_fire(
            EVENT_DOSE_GIVEN,
            {
                "cat": self.entry.title,
                "subentry_id": subentry.subentry_id,
                "item": subentry.title,
                "user": event["user"],
            },
            context=context,
        )
        self.async_notify()

    async def async_log_measurement(
        self, subentry: ConfigSubentry, value: float, context: Context | None
    ) -> None:
        """Log a measured value."""
        event = await self._async_log(subentry, context, value)
        await self._async_save()
        self.hass.bus.async_fire(
            EVENT_MEASUREMENT_LOGGED,
            {
                "cat": self.entry.title,
                "subentry_id": subentry.subentry_id,
                "item": subentry.title,
                "value": value,
                "unit": subentry.data.get(CONF_UNIT) or "",
                "user": event["user"],
            },
            context=context,
        )
        self.async_notify()

    async def async_set_stock(self, subentry: ConfigSubentry, value: float) -> None:
        """Set stock, e.g. after opening a new inhaler."""
        self._item(subentry.subentry_id)["stock"] = value
        await self._async_save()
        self.async_notify()
