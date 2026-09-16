# AV Room — Flask Equipment Lending

AV Room is a Flask-based college AV equipment lending system designed for everyday use by students and staff. Students can create accounts, search live equipment availability, reserve a unit, view their bookings and cancel eligible reservations. Staff can operate the loan desk, check equipment out, process returns, transfer active loans and create additional admin accounts.

## Stack

- Flask
- Flask-SQLAlchemy
- SQLite by default, with `DATABASE_URL` available for a hosted database
- Vanilla HTML/CSS/JavaScript frontend
- Signed Flask session authentication
- Gunicorn for production serving

## What it supports

- Equipment categories: DSLR, Projector, Mic and Tripod
- Individual assets with unique asset tags
- Date-range availability with overlap protection
- Student registration and login
- Password hashing; plaintext passwords are never stored
- Maximum active booking limit (default 3)
- Maximum loan length (default 14 days)
- Deposit recorded from the equipment type
- Staff checkout and return workflow
- Automatic late-fee calculation capped at the deposit
- Refund amount after return
- Staff-only transfer workflow with an audit log
- Due-soon / overdue staff dashboard
- Admin creation from the staff dashboard
- Responsive mobile-friendly frontend
- GitHub Actions checks for syntax, seeding and application import

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
python app.py
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The app listens on `0.0.0.0:5000` by default.

## Main pages

- `/` — public availability landing page
- `/static/index.html` — availability search
- `/static/login.html` — login / student registration
- `/static/book.html` — reservation flow
- `/static/my-bookings.html` — student's booking history
- `/static/dashboard.html` — staff dashboard

## Admin accounts

The seed script creates the first admin using environment variables:

```bash
ADMIN_USERNAME=admin ADMIN_PASSWORD='use-a-strong-password' python seed.py
```

Defaults are `admin` and `avroom2026` for local/demo use only. Change these values before making the application accessible to real users.

After logging in as an admin, use **+ Add admin** on the staff dashboard to create another administrator with a username and password.

## Demo users

The seed script also creates:

```text
demo_student1 / demo12345
demo_student2 / demo12345
demo_student3 / demo12345
```

These accounts are intended for testing the student workflow.

## Configuration

Useful environment variables:

```text
SECRET_KEY=long-random-secret
DATABASE_URL=sqlite:///av_room.db
PORT=5000
MAX_CONCURRENT_BOOKINGS=3
MAX_LOAN_DAYS=14
SESSION_COOKIE_SECURE=true
```

For a production deployment, use a strong `SECRET_KEY`, HTTPS, `SESSION_COOKIE_SECURE=true`, and a persistent production database rather than local SQLite.

## Real-world workflow

1. A student opens the public site and searches for equipment by category and dates.
2. The student signs in or creates an account.
3. The reservation screen shows the selected unit, deposit and late-fee policy before confirmation.
4. The booking appears in **My bookings**.
5. Staff use the dashboard to check the item out when it is physically issued.
6. If ownership of an active loan changes, staff can transfer it to another student without changing the equipment unit or due date.
7. On return, staff mark the loan returned. The app calculates late days, late fee and refund.
8. Additional staff accounts can be created by an existing admin.

## Security notes

The frontend and backend are served by the same Flask application, so authentication is cookie/session based and there is no separate frontend server to configure. User passwords are hashed with Werkzeug. Admin-only operations are enforced on the server rather than relying on hidden frontend controls.

Do not publish a real production secret or production password in the repository. Prefer environment variables or your hosting provider's secret manager.

## Production serving

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

A reverse proxy such as Nginx can sit in front of Gunicorn when the application is deployed on a VPS.

## CI

GitHub Actions runs Python compilation, dependency installation, database seeding and application import checks on pushes and pull requests to `main`.
