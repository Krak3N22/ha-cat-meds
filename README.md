# Pet Care for Home Assistant

Keep track of your pets' medication, measurements and stock, shared across everyone in the household.

- **Medications** (e.g. an asthma inhaler): a *give dose* button, last given and by whom, next due, an overdue alert and stock that counts down.
- **Measurements** (e.g. weekly blood glucose): type in a value, get a history graph, next due and an overdue alert.

Everyone uses their own Home Assistant user, so you can see who gave what and when. The logbook shows entries like *"Freja got Inhaler from Alex"*.

## Install

HACS → ⋮ → Custom repositories → add `https://github.com/Krak3N22/ha-pet-care` as *Integration* → download → restart Home Assistant.
Manual install: copy `custom_components/pet_care` into your `config/custom_components/`.

Requires Home Assistant 2025.3 or newer (2026.3+ to show the integration icon).

## Setup

1. Settings → Devices & services → Add integration → **Pet Care** → enter your pet's name.
2. On the pet's entry, choose **Add medication** or **Add measurement**.
   - Schedule: times of day (`08:00, 20:00`) *or* every N days.
   - Medication: amount per dose, unit (e.g. puffs) and optional stock.
3. When you open a new inhaler, set the *stock* entity to the number of puffs.

A dose given up to 2 hours before a scheduled time counts for that time.

## Events

`pet_care_dose_given` and `pet_care_measurement_logged` are fired for use in automations.

## Development

```sh
pytest tests
```
