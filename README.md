# AV Room — Flask + Firebase Equipment Lending

AV Room is a Flask-based college AV equipment lending system. Firebase Authentication handles user identity, and Cloud Firestore is the persistent application database. Flask remains responsible for server-side business rules and protected staff operations.

## Stack

- Flask
- Firebase Authentication (Email/Password)
- Firebase Admin SDK
- Cloud Firestore
- Vanilla HTML/CSS/JavaScript frontend
- Gunicorn for production serving

## Features

- Public equipment availability search
- Student account registration and Firebase sign-in
- Persistent Firestore users, equipment, bookings and transfer logs
- Individual asset tags for cameras, projectors, microphones and tripods
- Date-range overlap protection
- Maximum active booking limit (default 3)
- Maximum loan length (default 14 days)
- Deposit and daily late-fee calculation
- Student booking history and cancellation of eligible reservations
- Staff checkout, return and loan transfer
- Late-fee cap and refund calculation
- Admin-only management actions
- Existing admins can create additional Firebase admin accounts
- Responsive mobile-friendly frontend

## Firebase setup

1. Open the Firebase Console for project `avroom-7c3cb`.
2. Enable **Authentication → Sign-in method → Email/Password**.
3. Create a **Cloud Firestore** database.
4. Apply `firestore.rules` from this repository. Client-side Firestore reads/writes are intentionally blocked because the Flask backend uses the Admin SDK for database access.
5. In **Project settings → Service accounts**, create a Firebase Admin SDK service-account key.
6. Do not commit that JSON key. The repository ignores service-account files.

For local development, either provide the service-account file as `firebase-service-account.json` or set:

```text
FIREBASE_SERVICE_ACCOUNT_FILE=/full/path/to/firebase-service-account.json
```

For hosting platforms that support secret environment variables, prefer:

```text
FIREBASE_SERVICE_ACCOUNT_JSON={...entire service-account JSON...}
```

Firebase's recommended pattern for a custom backend is to send the client's Firebase ID token to the server and verify it with the Firebase Admin SDK before trusting the user identity.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
python app.py
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

The app listens on `0.0.0.0:5000` by default.

## Pages

- `/` — public availability page
- `/static/index.html` — availability search
- `/static/login.html` — Firebase login / registration
- `/static/book.html` — reservation flow
- `/static/my-bookings.html` — student bookings
- `/static/dashboard.html` — staff dashboard

## Initial admin and demo data

Set a real admin email/password before seeding:

```bash
ADMIN_USERNAME=admin ADMIN_EMAIL=admin@your-college-domain.example ADMIN_PASSWORD='use-a-strong-password' python seed.py
```

For local/demo use, the defaults are:

```text
Admin email: admin@avroom.local
Admin username: admin
Admin password: avroom2026

Demo student emails:
demo_student1@avroom.local
demo_student2@avroom.local
demo_student3@avroom.local
Password: demo12345
```

Firebase Authentication uses the email address for sign-in. The application also stores the chosen username in Firestore so staff can identify borrowers.

## Real-world storage

Application records are stored in Cloud Firestore, not SQLite. Restarting Flask does not delete Firestore data, and different users connected to the deployed application see the same database.

Firestore collections used by the Flask backend:

```text
users/
equipment_types/
equipment_units/
bookings/
transfer_logs/
```

The Flask server verifies Firebase ID tokens and then reads/writes Firestore using the Firebase Admin SDK. This follows Firebase's server-side token verification model.

## Configuration

```text
SECRET_KEY=long-random-secret
FIREBASE_SERVICE_ACCOUNT_FILE=/path/to/firebase-service-account.json
FIREBASE_SERVICE_ACCOUNT_JSON={...}
PORT=5000
MAX_CONCURRENT_BOOKINGS=3
MAX_LOAN_DAYS=14
SESSION_COOKIE_SECURE=true
```

For production, use HTTPS, a strong `SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, and a secret manager/environment variables for Firebase credentials.

## Production

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

Place Nginx or your hosting provider's HTTPS proxy in front of Gunicorn.

## Health check

```text
GET /health
```

The response reports `storage: firebase-firestore` when the Flask service is running.

## CI

GitHub Actions installs the Python dependencies and checks that the Flask/Firebase integration files compile and are present. It does not need a production Firebase service-account secret during syntax checks.
