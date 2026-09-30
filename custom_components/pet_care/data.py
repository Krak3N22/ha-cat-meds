"""Persistent data for one pet: event log and stock per tracked item."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import schedule
from .const import (
    CONF_DOSE_AMOUNT,
    CONF_GUARD_HOURS,
    CONF_INTERVAL_DAYS,
    CONF_STOCK,
    CONF_TIMES,
    CONF_TRACK_STOCK,
    CONF_UNIT,
    DEFAULT_GUARD_HOURS,
    DOMAIN,
    EVENT_DOSE_GIVEN,
    EVENT_MEASUREMENT_LOGGED,
    EVENT_UNDONE,
    MAX_EVENTS,
    signal_update,
)

STORAGE_VERSION = 1

# Pressing "give dose" again within this time confirms a double dose.
CONFIRM_WINDOW = timedelta(seconds=30)
# Only recent mistakes can be undone.
UNDO_WINDOW = timedelta(hours=24)
# Allow for clocks that are slightly off.
FUTURE_TOLERANCE = timedelta(minutes=5)


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


class PetCareData:
    """Event log and stock for all items of one pet (config entry)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._items: dict[str, dict[str, Any]] = {}
        # subentry_id -> when a double dose was refused, awaiting confirmation
        self._confirm: dict[str, float] = {}

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

    async def _async_user(self, context: Context | None) -> tuple[str | None, str | None]:
        user_id = context.user_id if context else None
        user = await self.hass.auth.async_get_user(user_id) if user_id else None
        return user_id, user.name if user else None

    def _add_event(
        self, subentry: ConfigSubentry, event: dict[str, Any]
    ) -> None:
        events = self._item(subentry.subentry_id)["events"]
        events.append(event)
        # Backdated events go in their right place; the last one is the latest.
        events.sort(key=_event_time)
        del events[:-MAX_EVENTS]

    def _check_when(self, when: datetime | None) -> datetime:
        now = dt_util.utcnow()
        if when is None:
            return now
        when = dt_util.as_utc(when)
        if when > now + FUTURE_TOLERANCE:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="in_future"
            )
        return when

    def _check_double_dose(
        self, subentry: ConfigSubentry, when: datetime, force: bool
    ) -> None:
        """Refuse a dose close to another one, unless confirmed.

        Pressing again within CONFIRM_WINDOW confirms that it was intended.
        """
        guard = float(subentry.data.get(CONF_GUARD_HOURS, DEFAULT_GUARD_HOURS))
        events = self._item(subentry.subentry_id)["events"]
        if force or not guard or not events:
            self._confirm.pop(subentry.subentry_id, None)
            return
        nearest = min(events, key=lambda e: abs(_event_time(e) - when))
        if abs(_event_time(nearest) - when) >= timedelta(hours=guard):
            self._confirm.pop(subentry.subentry_id, None)
            return
        asked = self._confirm.get(subentry.subentry_id)
        if asked is not None and monotonic() - asked <= CONFIRM_WINDOW.total_seconds():
            self._confirm.pop(subentry.subentry_id, None)
            return
        self._confirm[subentry.subentry_id] = monotonic()
        user = nearest.get("user")
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="already_given_by" if user else "already_given",
            translation_placeholders={
                "item": subentry.title,
                "time": format_time(_event_time(nearest)),
                "user": user or "",
                "seconds": str(int(CONFIRM_WINDOW.total_seconds())),
            },
        )

    async def async_give_dose(
        self,
        subentry: ConfigSubentry,
        context: Context | None,
        when: datetime | None = None,
        force: bool = False,
    ) -> None:
        """Log a dose and take it out of stock."""
        when = self._check_when(when)
        self._check_double_dose(subentry, when, force)
        user_id, user = await self._async_user(context)
        event: dict[str, Any] = {
            "ts": when.isoformat(),
            "logged": dt_util.utcnow().isoformat(),
            "user_id": user_id,
            "user": user,
        }
        item = self._item(subentry.subentry_id)
        if subentry.data.get(CONF_TRACK_STOCK):
            amount = float(subentry.data.get(CONF_DOSE_AMOUNT, 1))
            event["amount"] = amount
            item["stock"] = max(0.0, item.get("stock", 0.0) - amount)
        self._add_event(subentry, event)
        await self._async_save()
        self.hass.bus.async_fire(
            EVENT_DOSE_GIVEN,
            {
                "pet": self.entry.title,
                "subentry_id": subentry.subentry_id,
                "item": subentry.title,
                "user": user,
                "given_at": event["ts"],
            },
            context=context,
        )
        self.async_notify()

    async def async_log_measurement(
        self,
        subentry: ConfigSubentry,
        value: float,
        context: Context | None,
        when: datetime | None = None,
    ) -> None:
        """Log a measured value."""
        when = self._check_when(when)
        user_id, user = await self._async_user(context)
        event = {
            "ts": when.isoformat(),
            "logged": dt_util.utcnow().isoformat(),
            "user_id": user_id,
            "user": user,
            "value": value,
        }
        self._add_event(subentry, event)
        await self._async_save()
        self.hass.bus.async_fire(
            EVENT_MEASUREMENT_LOGGED,
            {
                "pet": self.entry.title,
                "subentry_id": subentry.subentry_id,
                "item": subentry.title,
                "value": value,
                "unit": subentry.data.get(CONF_UNIT) or "",
                "user": user,
                "measured_at": event["ts"],
            },
            context=context,
        )
        self.async_notify()

    async def async_undo(self, subentry: ConfigSubentry, context: Context | None) -> None:
        """Remove the most recently logged event and give back its stock."""
        item = self._item(subentry.subentry_id)
        events = item["events"]
        if not events:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="nothing_to_undo"
            )
        # Undo what was logged last, even if it was backdated.
        latest = max(events, key=lambda e: dt_util.parse_datetime(e.get("logged", e["ts"])))
        logged = dt_util.parse_datetime(latest.get("logged", latest["ts"]))
        if dt_util.utcnow() - logged > UNDO_WINDOW:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="nothing_to_undo"
            )
        events.remove(latest)
        if "amount" in latest and "stock" in item:
            item["stock"] = item["stock"] + latest["amount"]
        self._confirm.pop(subentry.subentry_id, None)
        _, user = await self._async_user(context)
        await self._async_save()
        self.hass.bus.async_fire(
            EVENT_UNDONE,
            {
                "pet": self.entry.title,
                "subentry_id": subentry.subentry_id,
                "item": subentry.title,
                "user": user,
                "undone_at": latest["ts"],
            },
            context=context,
        )
        self.async_notify()

    async def async_set_stock(self, subentry: ConfigSubentry, value: float) -> None:
        """Set stock, e.g. after opening a new inhaler."""
        self._item(subentry.subentry_id)["stock"] = value
        await self._async_save()
        self.async_notify()


def _event_time(event: dict[str, Any]) -> datetime:
    return dt_util.parse_datetime(event["ts"])


def format_time(when: datetime) -> str:
    """Format as "16:46", or "2026-09-29 16:46" if not today."""
    local = dt_util.as_local(when)
    if local.date() == dt_util.now().date():
        return local.strftime("%H:%M")
    return local.strftime("%Y-%m-%d %H:%M")
