# Availability test data

Use the **test data table** to verify availability and booking before relying on staff calendars.

## Table: `availability_test_slots`

- **slot_date** – date (YYYY-MM-DD)
- **slot_time** – time (HH:MM, e.g. 09:00, 09:30)
- **service_id** – optional; `NULL` = any service
- **active** – 1 = offered, 0 = disabled

Slots are seeded for the next 7 days with sample times (09:00–16:00) when the database is first seeded.

## Enable test mode

Set the environment variable so the API uses the test table instead of the calendar:

```bash
export USE_AVAILABILITY_TEST_DATA=1
```

Or in `.env` / Docker / K8s:

```
USE_AVAILABILITY_TEST_DATA=1
```

Accepted values: `1`, `true`, `yes` (case-insensitive).

## What to test

1. **GET /api/appointments/available-slots?date=YYYY-MM-DD&service_id=...**  
   Should return a list of times (e.g. `["09:00", "09:30", ...]`) from `availability_test_slots` for that date.

2. **Create appointment**  
   Pick one of those times and create an appointment (frontend or API). Confirm it succeeds and appears in the list.

3. **Turn off test mode**  
   Unset `USE_AVAILABILITY_TEST_DATA` (or set to `0`/`false`). Restart the app. Available slots should now come from staff schedules (calendar).

## Reseed test slots

If the table is empty, rerun seed so test slots are repopulated:

```python
from database import seed_availability_test_slots
seed_availability_test_slots(days_ahead=7)  # optional: customize days or times
```

Or restart the app after clearing the table; the normal `seed_data()` only inserts when the table has no rows.
