# AV Room

A Django-based college AV equipment lending system. Students can check availability and reserve equipment; staff can manage checkout, returns, deposits, late fees, refunds, and due-date reminders.

## Features

- Equipment types: DSLR, Projector, Mic, Tripod
- Individual equipment units with unique asset tags and lifecycle status
- Date-range availability checking with overlap detection
- Student booking flow with a server-side concurrent-booking limit
- Automatic deposit charging from the equipment type
- Django admin checkout and return actions
- Late-fee calculation capped at the charged deposit
- Refund amount shown as deposit minus late fee
- Staff dashboard for due-soon and overdue checked-out items
- Console-email due reminders with a daily GitHub Actions workflow
- Repeatable demo data seeding

## Run in GitHub Codespaces

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Open the forwarded port 8000 in your browser.

## Demo data

Run:

```bash
python manage.py seed_demo_data
```

This creates four equipment types, three units per type, three demo students, and sample on-time/overdue bookings. Demo passwords are `demo12345`.

## Main URLs

- `/availability/` — choose a category and date range to see free-unit counts and asset tags.
- `/bookings/new/` — authenticated student booking form.
- `/dashboard/` — staff dashboard for due-soon and overdue checked-out bookings.
- `/admin/` — Django admin for equipment and booking management.

## Booking rules

A booking is rejected when the selected unit has an active (`reserved` or `checked_out`) booking overlapping the requested range. The overlap rule is `start < other.due_date and end > other.start_date`.

Each borrower may have at most `MAX_CONCURRENT_BOOKINGS` active bookings at once. The default is 3 and can be overridden with the environment variable of the same name.

On successful creation, the booking is saved as `reserved` and its deposit is copied from the equipment type.

## Checkout and return walkthrough

1. Create or seed an EquipmentType and EquipmentUnit in `/admin/`.
2. Log in as a student and use `/bookings/new/` to reserve a unit.
3. In Django admin, select the reservation and choose **Check out selected bookings**. The booking becomes `checked_out` and the unit becomes `checked_out`.
4. When the item comes back, select the booking and choose **Mark selected bookings returned**.
5. The system records today's return date, calculates late days, applies `daily_late_fee`, caps the fee at the deposit, makes the unit available again, and displays the refund amount in admin.

## Reminder command

```bash
python manage.py send_due_reminders
```

The command targets checked-out bookings due tomorrow or already overdue. Email uses Django's console backend, so reminder messages are visible in the terminal.

## Tests

```bash
python manage.py test
```

The inventory test suite covers availability, double-booking rejection, the maximum active-booking limit, valid reservation/deposit assignment, and on-time/late/capped return fee calculations.
