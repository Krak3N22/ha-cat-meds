# Pet Care for Home Assistant

Keep track of your pets' medication, measurements and stock, shared across everyone in the household.

- **Medications** (e.g. an asthma inhaler): a *give dose* button, last given and by whom, next due, an overdue alert and stock that counts down.
- **Measurements** (e.g. weekly blood glucose): type in a value, get a history graph, next due and an overdue alert.

Everyone uses their own Home Assistant user, so you can see who gave what and when. The logbook shows entries like *"Freja got Inhaler from Alex"*.

- **Double dose guard:** pressing *give dose* soon after someone else did shows *"Inhaler was already given at 16:46 by Alex"*. Press again within 30 seconds if you really meant it. The window is set per medication (default 2 hours, 0 = off).
- **Undo:** each item has an *undo latest* button (under Configuration on the device) that removes the latest entry from the last 24 hours and puts the stock back.
- **Log afterwards:** the `pet_care.give_dose` and `pet_care.log_measurement` actions take an optional time.

> Pet Care helps you remember. It is not a medical device; always follow your vet's advice.

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

## Actions

| Action | Target | Fields |
|---|---|---|
| `pet_care.give_dose` | a *give dose* button | `given_at` (optional), `force` (skip the double dose guard) |
| `pet_care.log_measurement` | a *log value* number | `value`, `measured_at` (optional) |
| `pet_care.undo` | any entity of the item | |

To log a dose afterwards from a dashboard, create this script and add it as a button. Home Assistant asks for the time when you run it:

```yaml
alias: Inhaler given earlier
fields:
  given_at:
    name: Given at
    required: true
    selector:
      datetime:
sequence:
  - action: pet_care.give_dose
    target:
      entity_id: button.freja_inhaler_give_dose
    data:
      given_at: "{{ given_at }}"
```

## Events

`pet_care_dose_given`, `pet_care_measurement_logged` and `pet_care_undone` are fired for use in automations.

## Development

```sh
pip install -r requirements_test.txt
pytest
```

Tests and validation (hassfest, HACS) run on GitHub Actions for every pull request.
