# AV Room

AV Room is a Django college AV equipment lending system. Students can check availability and reserve equipment; staff can manage checkout, returns, transfers, deposits, late fees, refunds, and due-date reminders.

## Stack

- Django
- Django REST Framework
- SQLite for development
- Python 3.12 / GitHub Codespaces
- Vanilla HTML/CSS/JavaScript frontend

## Features

- Equipment types: DSLR, Projector, Mic, Tripod
- Individual equipment units with unique asset tags and lifecycle status
- Date-range availability checking with overlap detection
- Student booking with server-side `MAX_CONCURRENT_BOOKINGS` limit (default 3)
- Automatic deposit charging from the equipment type
- Staff checkout and return actions in Django admin
- Late fees capped at the charged deposit and refund calculation
- Loan transfer between borrowers without changing the equipment unit, date window, status, or availability
- Transfer audit log with source, destination, timestamp, and staff performer
- Staff dashboard for due-soon and overdue checked-out items
- Console-email due reminders and daily GitHub Actions scheduling
- Repeatable demo-data seeding
- REST API for availability, booking, checkout, return, transfer, dashboard, and borrower lookup
- Plain HTML/CSS/JS frontend with loading, error, and empty states

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

In Codespaces, open forwarded port `8000`.

## Frontend URLs

- `http://localhost:8000/` — redirects to the availability page
- `http://localhost:8000/static/index.html` — availability search
- `http://localhost:8000/static/book.html` — student booking
- `http://localhost:8000/static/dashboard.html` — staff dashboard
- `http://localhost:8000/admin/` — Django admin
- `http://localhost:8000/accounts/login/` — Django session login

## API URLs

- `GET /api/availability/?category=&start_date=&end_date=`
- `POST /api/bookings/`
- `POST /api/bookings/<id>/checkout/`
- `POST /api/bookings/<id>/return/`
- `POST /api/bookings/<id>/transfer/` with `{ "new_borrower_id": 123 }`
- `GET /api/dashboard/`
- `GET /api/borrowers/` (staff only, used by the transfer selector)

DRF uses Django session authentication and the same-origin CSRF token for POST requests. CORS is not configured because the frontend is served by Django from the same origin.

## Demo data

```bash
python manage.py seed_demo_data
```

This creates four equipment types, three units per type, three demo students, plus one on-time and one overdue checked-out booking. Demo password: `demo12345`.

## Booking rules

An active booking is `reserved` or `checked_out`. A unit is unavailable when an active booking overlaps the requested range using `start < other.due_date and end > other.start_date`.

A borrower may have at most `MAX_CONCURRENT_BOOKINGS` active bookings. The default is 3 and can be overridden with the environment variable `MAX_CONCURRENT_BOOKINGS`.

Successful bookings are saved as `reserved`, with `deposit_charged` copied from the equipment type.

## Checkout and return

Staff use the Booking admin actions **Check out selected bookings** and **Mark selected bookings returned**. Checkout changes the booking and unit to `checked_out`. Return records today's date, calculates late days, applies the equipment type's daily late fee, caps it at the deposit, returns the unit to `available`, and shows `refund_amount = deposit_charged - late_fee_charged`.

## Transfers

A transfer is a mutation of an existing checked-out booking. It changes only the borrower and creates a `TransferLog`. The equipment unit stays `checked_out`, so its availability window does not change and no availability check is performed. The new borrower must still be below `MAX_CONCURRENT_BOOKINGS`.

Staff can transfer from Django admin using the **Transfer to another borrower** action, or through `POST /api/bookings/<id>/transfer/`.

## Reminders

```bash
python manage.py send_due_reminders
```

The command finds checked-out bookings due tomorrow or overdue and sends via Django's console email backend, while also printing the reminder. `.github/workflows/reminders.yml` schedules the command daily and can be adapted when persistent production email/data storage is available.

## Tests

```bash
python manage.py check
python manage.py test
```

GitHub Actions runs the same checks on pushes and pull requests to `main`.
