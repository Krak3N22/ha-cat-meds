"""Constants for Pet Care."""

DOMAIN = "pet_care"

# Subentry types: one per thing we track for a pet.
SUBENTRY_DOSE = "dose"  # medication given in doses, e.g. an inhaler
SUBENTRY_MEASUREMENT = "measurement"  # a logged value, e.g. blood glucose

CONF_DOSE_AMOUNT = "dose_amount"
CONF_UNIT = "unit"
CONF_TIMES = "times"
CONF_INTERVAL_DAYS = "interval_days"
CONF_TRACK_STOCK = "track_stock"
CONF_STOCK = "stock"
CONF_GUARD_HOURS = "guard_hours"

DEFAULT_GUARD_HOURS = 2

EVENT_DOSE_GIVEN = f"{DOMAIN}_dose_given"
EVENT_MEASUREMENT_LOGGED = f"{DOMAIN}_measurement_logged"
EVENT_UNDONE = f"{DOMAIN}_undone"

MAX_EVENTS = 200


def signal_update(entry_id: str) -> str:
    """Dispatcher signal fired when an entry's data changes."""
    return f"{DOMAIN}_update_{entry_id}"
