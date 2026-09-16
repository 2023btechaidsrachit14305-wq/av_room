
Recommended stack (why)

Django + SQLite (dev) + Django admin. Reasons specific to your requirements:

Django admin gives you a working staff dashboard (check items in/out) for free, no frontend work needed to get functional.
Built-in auth covers "borrower" accounts immediately.
Its ORM handles the relational bits you need (units, bookings, dates) cleanly.
django-crontab or a simple management command covers the "nudge" reminders without needing a task queue.

If you'd rather use Node/Express or Flask, the same phase structure works — just adapt the prompts.

Data model (decide this before prompting anything)
EquipmentType — name, category (DSLR/Projector/Mic/Tripod), deposit amount, daily late fee
EquipmentUnit — belongs to an EquipmentType, serial/asset tag, status (available/booked/out/maintenance) — this is what makes "popular items have several units" work: you book a unit, not a type
Borrower — Django User + student ID/contact
Booking — borrower, unit, start date, due date, returned date (nullable), deposit charged, late fee charged, status
BookingLimit rule — max units a borrower can hold at once (config value, not a model)
Phase 1 — Repo & Codespace scaffold
Create a new Django project called "av_room" for a college AV equipment
lending system. Set up:
- A devcontainer.json configured for Python 3.12, so it works in GitHub
  Codespaces out of the box
- requirements.txt with django and python-dotenv
- A Django app called "inventory"
- .gitignore for Python/Django
- SQLite as the dev database
Run the initial migration and confirm the dev server starts. Give me the
exact commands to run inside the Codespace terminal.

Check: Codespace boots, python manage.py runserver works, you see the default Django page.

Phase 2 — Data models
In the "inventory" app, create these models:

EquipmentType: name, category (choices: DSLR, Projector, Mic, Tripod),
deposit_amount (decimal), daily_late_fee (decimal)

EquipmentUnit: foreign key to EquipmentType, asset_tag (unique string),
status (choices: available, booked, checked_out, maintenance)

Booking: foreign key to Django User (borrower), foreign key to
EquipmentUnit, start_date, due_date, returned_date (nullable),
deposit_charged (decimal), late_fee_charged (decimal, default 0),
status (choices: reserved, checked_out, returned, cancelled)

Add __str__ methods, sensible Meta ordering, and register all three in
admin.py with list_display showing the key fields. Then create and run
the migration.

Check: python manage.py createsuperuser, log into /admin/, confirm you can add EquipmentTypes and Units by hand.

Phase 3 — Availability logic ("is a DSLR free this weekend?")
Add a method or manager to check availability:

1. A function `available_units(equipment_type, start_date, end_date)`
   that returns EquipmentUnits of that type with no overlapping Booking
   in status reserved/checked_out for that date range (overlap = start
   < other.due_date and end > other.start_date).

2. A simple view + template (or DRF endpoint if I say I want an API)
   at /availability/ where a student picks a category and a date range
   and sees a count of free units plus their asset tags.

Write a unit test that creates two units of one type, books one of them
for a date range, and asserts the availability function returns exactly
one free unit for an overlapping range and both for a non-overlapping one.

Check: run the test (python manage.py test), then manually hit /availability/.

Phase 4 — Booking flow with the business rules

This is the phase that encodes your actual constraints (deposit, per-day late fee, don't let one person hog the room).

Add a booking creation view/form (student-facing, login required) with
these rules enforced server-side, not just in the form:

1. Reject if the chosen unit is not available for the requested dates
   (reuse the availability check from before).
2. Reject if the borrower already has more than N active bookings
   (reserved + checked_out) at once — make N a settings.py constant
   called MAX_CONCURRENT_BOOKINGS, default 3.
3. On creation, set deposit_charged from the EquipmentType's
   deposit_amount and status to "reserved".
4. Show the borrower their deposit amount and due date clearly on
   confirmation.

Write tests: one for a rejected double-booking, one for a rejected
booking past MAX_CONCURRENT_BOOKINGS, one for a valid booking.

Check: try to book a 4th item as one test user and confirm it's rejected; confirm the reason is a clear error message, not a 500.

Phase 5 — Checkout & return flow (late fee + deposit refund)
Add two admin-facing actions on Booking (as Django admin actions, or a
small staff view if I want it outside admin):

1. "Check out" — sets status to checked_out, sets EquipmentUnit status
   to checked_out, records start_date if not already set.

2. "Mark returned" — sets returned_date to today, sets EquipmentUnit
   status back to available, calculates late_fee_charged:
   late_days = max(0, (returned_date - due_date).days)
   late_fee_charged = late_days * equipment_type.daily_late_fee
   capped at deposit_charged (fee can't exceed the deposit)
   Then compute and display refund_amount = deposit_charged - late_fee_charged.

Write tests for: on-time return (fee = 0, full refund), late return
(fee computed correctly), and a very late return where the fee is
capped at the deposit amount.

Check: run tests, then manually walk through checkout → return in admin for a unit you back-date the due_date on.

Phase 6 — Nudges (the reminder piece)
Add:
1. A staff dashboard view at /dashboard/ listing all bookings that are
   checked_out and either due within 2 days or already overdue, sorted
   by due_date, with days-overdue shown for overdue ones.
2. A Django management command `send_due_reminders` that finds bookings
   due tomorrow or overdue and prints/emails a reminder to the
   borrower (use Django's console email backend for now so I can see
   it in the terminal without real SMTP setup).
3. A GitHub Actions workflow (.github/workflows/reminders.yml) that
   runs this command on a daily cron schedule, so I have the option to
   automate it later once real email is configured.

Check: run python manage.py send_due_reminders by hand with a test overdue booking and confirm the console output looks right.

Phase 7 — Seed data & README
Create a management command `seed_demo_data` that populates:
- 4 EquipmentTypes (DSLR, Projector, Mic, Tripod) with realistic
  deposit amounts and daily late fees
- 2-3 EquipmentUnits per type
- 2-3 demo student users
- A couple of sample bookings (one on time, one overdue) so the
  dashboard has something to show

Then write a README.md covering: what the project does, how to run it
in Codespaces, how to seed demo data, and a short walkthrough of the
booking → checkout → return flow.
Phase 8 — Commit checkpoints

Run this after each phase so history stays clean:

git add -A && git commit -m "Phase N: <short description>"

One judgment call to flag: the "one person shouldn't book half the room" rule is implemented above as a flat cap (MAX_CONCURRENT_BOOKINGS). If you'd rather it scale with room size (e.g. no more than 20% of any one category), say so in the Phase 4 prompt and ask for a percentage-based check instead of a fixed number — it's a one-line change to that rule.

Want me to also sketch the percentage-based version of that rule, or help you pick between Django and a Node/React stack if you're more comfortable there?

now after this if this working Your solution must also allow an active loan to be transferred from one borrower to another — the original due date carries over unchanged, and the item’s availability is unaffected by the transfer.

Make the frontend with html css js

Building a money transfer feature with frontend and backend.

Good — transfers are a common real-world need (a club member has to drop something off before travel, another member picks it up). Here's how to add it cleanly, plus the frontend phase.

Design decision for transfer

Key point: a transfer is not a new booking. It's a mutation of the existing one — same EquipmentUnit, same due_date, same status=checked_out, just a different borrower on the record. That's what makes "availability unaffected" trivially true: the unit's status never changes, so your availability-overlap check (which only looks at unit status/bookings) never even runs during a transfer.

One judgment call: should the new borrower still be checked against MAX_CONCURRENT_BOOKINGS? I'd say yes — otherwise transfers become a loophole to dodge the room-hogging rule. I've baked that into the prompt below; flag it if you want it removed.

Phase 9 — Loan transfer logic
Add loan transfer capability to the "inventory" app:

1. Add a TransferLog model: foreign key to Booking, from_user, to_user,
   transferred_at (auto_now_add), transferred_by (staff user who
   performed it, nullable).

2. Add a `transfer_booking(booking, new_borrower, performed_by)`
   function (in a services.py file) that:
   - Rejects if booking.status is not "checked_out" (can't transfer a
     reservation that hasn't been picked up yet, or one already returned)
   - Rejects if new_borrower already has >= MAX_CONCURRENT_BOOKINGS
     active bookings
   - Rejects if new_borrower == booking.borrower (no-op transfer)
   - On success: sets booking.borrower = new_borrower, leaves
     due_date, start_date, deposit_charged, and the EquipmentUnit's
     status completely unchanged, creates a TransferLog entry, saves.
   - Does NOT touch availability/overlap logic at all — confirm in a
     code comment why: the unit stays checked_out throughout, so no
     availability windows open up.

3. Add a staff admin action "Transfer to another borrower" on the
   Booking admin that prompts for the new borrower and calls this
   function.

Write tests:
- Transferring a checked_out booking updates borrower, keeps due_date
  identical, keeps status checked_out.
- Transferring a "reserved" (not yet picked up) booking is rejected.
- Transferring to a borrower already at MAX_CONCURRENT_BOOKINGS is rejected.
- After a transfer, availability queries for that unit's date range
  still show it as unavailable (proving nothing opened up).
- TransferLog record is created with correct from/to users.

Check: run the tests, then in admin do a manual transfer on a checked-out booking and confirm the due date on screen doesn't change.

Phase 10 — API layer (needed before a JS frontend can talk to Django)

Vanilla HTML/CSS/JS needs endpoints to call, so add a thin API first:

Add Django REST Framework to the project:
- pip install djangorestframework, add to INSTALLED_APPS
- Create serializers for EquipmentType, EquipmentUnit, Booking
- Create these API endpoints under /api/:
  GET  /api/availability/?category=&start_date=&end_date=  -> list of
       free units
  POST /api/bookings/         -> create a booking (reuses Phase 4 rules)
  POST /api/bookings/<id>/checkout/   -> staff checkout
  POST /api/bookings/<id>/return/     -> staff return, returns
       computed late_fee and refund_amount in response
  POST /api/bookings/<id>/transfer/   -> body: {new_borrower_id},
       uses transfer_booking() from Phase 9
  GET  /api/dashboard/        -> due-soon and overdue bookings
- Use session auth (reuse Django login) so I don't need to build a
  separate token auth system yet.
- Add CORS headers only if I tell you the frontend will run on a
  different port; otherwise skip it since it'll be served from the
  same Django app.

Write a quick smoke test hitting each endpoint with the Django test client.

Check: hit each endpoint with curl or the DRF browsable API in the browser and confirm real JSON comes back.

Phase 11 — Frontend in plain HTML/CSS/JS
Create a static frontend (no framework, just HTML/CSS/vanilla JS) served
from Django's static files, with these pages:

1. static/index.html — "Check availability": category dropdown, date
   range pickers, a "Search" button that calls GET /api/availability/
   and renders a card per free unit with its asset tag.

2. static/book.html — booking form: unit selection (from availability
   results), start/due date, submit calls POST /api/bookings/ and
   shows either a confirmation with deposit amount and due date, or
   the server's rejection reason (overlap / too many active bookings)
   in a visible error banner, not a silent console error.

3. static/dashboard.html — staff view: table of due-soon/overdue
   bookings from GET /api/dashboard/, with inline buttons per row for
   "Check out", "Mark returned" (shows computed late fee + refund
   before confirming), and "Transfer" (dropdown/search for new
   borrower, calls the transfer endpoint, shows the unchanged due date
   after success so it's visibly confirmed).

Structure:
- static/css/styles.css — one shared stylesheet, clean and readable,
  not framework-heavy
- static/js/api.js — a small fetch wrapper handling the CSRF token
  Django needs for POST requests from session auth
- static/js/availability.js, booking.js, dashboard.js — one per page

Wire up Django's STATICFILES_DIRS so these are served in dev. Tell me
the exact URL to open for each page once the dev server is running.

Check: open index.html, search availability, book something, then go to dashboard.html and walk through checkout → transfer → return live in the browser.

Phase 12 — Polish pass (optional, do last)
Review static/css/styles.css and the three JS files. Improve:
- Loading states (disable buttons while a fetch is in flight)
- Error states (all API failures show a message, none fail silently)
- Empty states (no available units, no due-soon bookings)
Don't change any business logic, only presentation and UX.

Two things worth deciding before you run Phase 9: whether the new borrower should be exempt from MAX_CONCURRENT_BOOKINGS during a transfer (I defaulted to "no, still enforced"), and whether staff alone can initiate a transfer or a borrower should be able to request one themselves that staff approves. The prompt above assumes staff-only, which matches your admin-desk workflow — say the word if you want a self-service request flow instead.
