# Cat Meds for Home Assistant

Keep track of your cats' medication, measurements and stock, shared across everyone in the household.

- **Medications** (e.g. an asthma inhaler): a *give dose* button, last given (and by whom), next due, an overdue alert and stock that counts down.
- **Measurements** (e.g. weekly blood glucose): type in a value, get a history graph, next due and an overdue alert.

Everyone uses their own Home Assistant user, so you can see who gave what and when.

## Install

HACS → Custom repositories → add this repo as *Integration* → install → restart Home Assistant.
Manual install: copy `custom_components/cat_meds` into your `config/custom_components/`.

## Setup

1. Settings → Devices & services → Add integration → **Cat Meds** → enter the cat's name.
2. On the cat's entry, choose **Add medication** or **Add measurement**.
   - Schedule: times of day (`08:00, 20:00`) *or* every N days.
   - Medication: amount per dose, unit (e.g. puffs) and optional stock.
3. When you open a new inhaler, set the *stock* entity to the number of puffs.

A dose given up to 2 hours before a scheduled time counts for that time.

## Events

`cat_meds_dose_given` and `cat_meds_measurement_logged` are fired for use in automations.

## Development

```sh
pytest tests
```
