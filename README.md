# AV Room

AV Room is a Flask application for managing AV equipment bookings, checkouts, returns, and transfers. The app uses Firebase Authentication for login and Cloud Firestore as the application database.

## Project overview

- Flask server for booking workflows and admin actions
- Firebase Authentication for user login and identity
- Firestore for equipment, users, bookings, and transfer logs
- Plain HTML/CSS/JavaScript frontend
- Python-based seed script to initialize sample data

## Tech stack

- Python 3.11+
- Flask
- Firebase Admin SDK
- Firestore
- Vanilla JavaScript frontend
- Gunicorn for production serving

## Project structure

```text
av_room/
├── app.py                 # Flask app entry point
├── firebase_service.py    # Firebase/Firestore initialization
├── seed.py                # Create admin + demo data
├── firestore.rules        # Firestore access rules
├── static/                # Frontend HTML, CSS, JS
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable examples
├── README.md              # Project guide
└── .secrets/              # Local secret folder (ignored by Git)
```

## Prerequisites

Before starting the project, make sure you have:

- Python 3.11 or newer installed
- pip available
- Git installed
- A Firebase project with:
  - Email/Password authentication enabled
  - Firestore database enabled
  - A Firebase service account JSON key generated

## Setup

1. Clone the repository and move into it:

```bash
cd /workspaces/av_room
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a Firebase service account file and store it locally:

```bash
mkdir -p .secrets
```

Then place your Firebase service-account JSON file at:

```text
/workspaces/av_room/.secrets/firebase-service-account.json
```

5. Export the file path before running the app or the seed script:

```bash
export FIREBASE_SERVICE_ACCOUNT_FILE="/workspaces/av_room/.secrets/firebase-service-account.json"
```

You can also use the combined environment value if preferred:

```bash
export FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ...}'
```

6. Seed the database with admin and demo data:

```bash
python seed.py
```

## Default demo accounts

The seed script creates the following defaults for local testing:

```text
Admin email: admin@avroom.local
Admin username: admin
Admin password: avroom2026

Demo students:
demo_student1@avroom.local
demo_student2@avroom.local
demo_student3@avroom.local
Password for all demo students: demo12345
```

## Running the project

Start the Flask app:

```bash
export FIREBASE_SERVICE_ACCOUNT_FILE="/workspaces/av_room/.secrets/firebase-service-account.json"
python app.py
```

By default the app runs on port 5000. If port 5000 is already occupied, start on a different port:

```bash
export FIREBASE_SERVICE_ACCOUNT_FILE="/workspaces/av_room/.secrets/firebase-service-account.json"
PORT=5001 python app.py
```

Then open one of these URLs in a browser:

- http://127.0.0.1:5000
- http://127.0.0.1:5001

## Common routes

- `/` — public equipment availability page
- `/health` — health check endpoint
- `/static/login.html` — login page
- `/static/book.html` — make a booking
- `/static/my-bookings.html` — borrower bookings
- `/static/dashboard.html` — admin dashboard

## Environment variables

Use these variables when needed:

```bash
SECRET_KEY="replace-with-a-long-random-string"
FIREBASE_SERVICE_ACCOUNT_FILE="/full/path/to/firebase-service-account.json"
FIREBASE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
PORT=5000
MAX_CONCURRENT_BOOKINGS=3
MAX_LOAN_DAYS=14
SESSION_COOKIE_SECURE=false
```

## Production-style run

For production or a hosting setup, use Gunicorn:

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

## Debugging and troubleshooting

### 1. Firebase credentials error

If the app fails with a message like:

```text
google.auth.exceptions.DefaultCredentialsError: Your default credentials were not found
```

then Firebase is not configured for this environment. Fix it by exporting either:

```bash
export FIREBASE_SERVICE_ACCOUNT_FILE="/workspaces/av_room/.secrets/firebase-service-account.json"
```

or by setting the JSON value directly.

### 2. Port already in use

If Flask reports that port 5000 is already in use:

```text
Address already in use
```

then either stop the other process or run the app on another port:

```bash
PORT=5001 python app.py
```

### 3. App starts but API routes fail

Check that the app can read the Firebase credentials and that the Firestore project is active. The app will return a 503 for Firebase-dependent routes when credentials are missing.

### 4. Seed script issues

Run:

```bash
export FIREBASE_SERVICE_ACCOUNT_FILE="/workspaces/av_room/.secrets/firebase-service-account.json"
python seed.py
```

This creates the admin account and the demo equipment/booking data.

### 5. Health check

Verify the service is responding:

```bash
curl http://127.0.0.1:5000/health
```

or:

```bash
curl http://127.0.0.1:5001/health
```

### 6. Quick Python validation

To check whether the app module imports successfully:

```bash
python -c "import app; print('import ok')"
```

## Firebase and Firestore notes

The app stores records in Firestore, not SQLite. Restarting the server does not clear Firestore data.

Main collections:

```text
users/
equipment_types/
equipment_units/
bookings/
transfer_logs/
```

## Security notes

- Do not commit Firebase service-account JSON files to Git
- Use environment variables or a secret manager in real deployments
- Use HTTPS in production
- Rotate the `SECRET_KEY` and avoid hardcoded credentials in source control

## CI and automated checks

The repository includes GitHub Actions checks for installation and basic validation. These checks are intentionally lightweight and do not require a full production Firebase configuration to pass.
