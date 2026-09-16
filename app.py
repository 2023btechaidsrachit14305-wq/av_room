import os
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, request, session
from firebase_admin import auth as firebase_auth
from firebase_admin import firestore
from werkzeug.middleware.proxy_fix import ProxyFix

from firebase_admin import db

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

MAX_CONCURRENT_BOOKINGS = int(os.environ.get("MAX_CONCURRENT_BOOKINGS", "3"))
MAX_LOAN_DAYS = int(os.environ.get("MAX_LOAN_DAYS", "14"))
ACTIVE_STATUSES = {"reserved", "checked_out"}

USERS = "users"
TYPES = "equipment_types"
UNITS = "equipment_units"
BOOKINGS = "bookings"
TRANSFER_LOGS = "transfer_logs"


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def clean_doc(ref):
    value = ref.to_dict() or {}
    value["id"] = ref.id
    return value


def current_user():
    uid = session.get("firebase_uid")
    if not uid:
        return None
    snap = db.collection(USERS).document(uid).get()
    if not snap.exists:
        return None
    user = snap.to_dict()
    user["uid"] = uid
    return user


def user_payload(user):
    return {
        "id": user.get("uid"),
        "username": user.get("username", ""),
        "name": user.get("full_name", ""),
        "email": user.get("email"),
        "role": user.get("role", "student"),
        "is_staff": user.get("role") == "admin",
        "is_superuser": user.get("role") == "admin",
    }


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("is_active", True) is False:
            return jsonify({"detail": "Authentication required."}), 401
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("is_active", True) is False:
            return jsonify({"detail": "Authentication required."}), 401
        if user.get("role") != "admin":
            return jsonify({"detail": "Admin access required."}), 403
        return f(*args, **kwargs)
    return wrapper


def body():
    return request.get_json(silent=True) or {}


def type_payload(doc):
    return {
        "id": doc.id,
        "name": doc.get("name", ""),
        "category": doc.get("category", ""),
        "deposit_amount": float(doc.get("deposit_amount", 0)),
        "daily_late_fee": float(doc.get("daily_late_fee", 0)),
    }


def unit_payload(doc):
    data = doc.to_dict() or {}
    type_doc = db.collection(TYPES).document(data["type_id"]).get()
    et = type_payload(type_doc) if type_doc.exists else {
        "id": data["type_id"], "name": "Unknown", "category": "Unknown", "deposit_amount": 0, "daily_late_fee": 0
    }
    return {
        "id": doc.id,
        "asset_tag": data.get("asset_tag", ""),
        "status": data.get("status", "available"),
        "equipment_type": et,
    }


def booking_payload(doc):
    data = doc.to_dict() or {}
    borrower_snap = db.collection(USERS).document(data["borrower_id"]).get()
    unit_snap = db.collection(UNITS).document(data["unit_id"]).get()
    borrower = borrower_snap.to_dict() if borrower_snap.exists else {}
    unit = unit_payload(unit_snap) if unit_snap.exists else {"id": data["unit_id"], "asset_tag": "Unknown", "name": "Unknown", "category": "Unknown"}
    deposit = float(data.get("deposit_charged", 0))
    late_fee = float(data.get("late_fee_charged", 0))
    return {
        "id": doc.id,
        "borrower": user_payload({**borrower, "uid": data["borrower_id"]}),
        "borrower_id": data["borrower_id"],
        "equipment_unit": unit,
        "start_date": data["start_date"],
        "due_date": data["due_date"],
        "returned_date": data.get("returned_date"),
        "deposit_charged": deposit,
        "late_fee_charged": late_fee,
        "refund_amount": max(0, deposit - late_fee),
        "status": data.get("status", "reserved"),
        "created_at": data.get("created_at"),
    }


def parse_date(value):
    return date.fromisoformat(value)


def active_bookings():
    return [
        (snap, snap.to_dict() or {})
        for snap in db.collection(BOOKINGS).where("status", "in", list(ACTIVE_STATUSES)).stream()
    ]


def overlap(unit_id, start, end, ignore_booking=None):
    for snap, data in active_bookings():
        if ignore_booking and snap.id == ignore_booking:
            continue
        if data.get("unit_id") != unit_id:
            continue
        other_start = parse_date(data["start_date"])
        other_due = parse_date(data["due_date"])
        if other_start < end and other_due > start:
            return True
    return False


def active_count(uid):
    return sum(1 for _, data in active_bookings() if data.get("borrower_id") == uid)


@app.get("/")
def home():
    return app.send_static_file("index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "av-room", "storage": "firebase-firestore"})


@app.get("/api/auth/me/")
@app.get("/api/me")
def me():
    user = current_user()
    ok = bool(user)
    return jsonify({"authenticated": ok, "user": user_payload(user) if ok else None})


@app.post("/api/auth/firebase-login/")
@app.post("/api/firebase-login")
def firebase_login():
    token = body().get("id_token") or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        return jsonify({"detail": "Firebase ID token is required."}), 401
    try:
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
    except Exception:
        return jsonify({"detail": "Invalid or expired Firebase session."}), 401

    uid = decoded["uid"]
    email = decoded.get("email")
    display_name = decoded.get("name") or (email.split("@")[0] if email else uid[:8])
    ref = db.collection(USERS).document(uid)
    snap = ref.get()
    if snap.exists:
        data = snap.to_dict() or {}
        data.update({"email": email or data.get("email"), "full_name": data.get("full_name") or display_name, "updated_at": now_iso()})
        ref.set(data, merge=True)
    else:
        username = (email.split("@")[0] if email else uid[:12]).lower()
        ref.set({"username": username, "full_name": display_name, "email": email, "role": "student", "is_active": True, "created_at": now_iso(), "updated_at": now_iso()})
    session.clear()
    session["firebase_uid"] = uid
    user = ref.get().to_dict() or {}
    user["uid"] = uid
    return jsonify({"authenticated": True, "user": user_payload(user)})


@app.post("/api/auth/register-profile/")
def register_profile():
    token = body().get("id_token")
    if not token:
        return jsonify({"detail": "Firebase ID token is required."}), 401
    try:
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
    except Exception:
        return jsonify({"detail": "Invalid Firebase ID token."}), 401
    uid = decoded["uid"]
    data = body()
    first = str(data.get("first_name", "")).strip()
    last = str(data.get("last_name", "")).strip()
    username = str(data.get("username", "")).strip().lower()
    email = decoded.get("email")
    if not first or not username:
        return jsonify({"detail": "First name and username are required."}), 400
    existing = db.collection(USERS).where("username", "==", username).limit(1).stream()
    existing_docs = [doc for doc in existing if doc.id != uid]
    if existing_docs:
        return jsonify({"detail": "That username is already taken."}), 400
    ref = db.collection(USERS).document(uid)
    ref.set({"username": username, "full_name": f"{first} {last}".strip(), "email": email, "role": "student", "is_active": True, "created_at": now_iso(), "updated_at": now_iso()}, merge=True)
    session.clear()
    session["firebase_uid"] = uid
    user = ref.get().to_dict() or {}
    user["uid"] = uid
    return jsonify({"authenticated": True, "user": user_payload(user)}), 201


@app.post("/api/auth/logout/")
@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"authenticated": False})


@app.get("/api/equipment-types")
def equipment_types():
    docs = db.collection(TYPES).stream()
    return jsonify([type_payload(doc) for doc in docs])


@app.get("/api/availability/")
@app.get("/api/availability")
def availability():
    category = request.args.get("category", "").strip()
    start_s = request.args.get("start_date") or request.args.get("start")
    end_s = request.args.get("end_date") or request.args.get("end")
    if not start_s or not end_s:
        return jsonify({"detail": "Start date and end date are required."}), 400
    try:
        start, end = parse_date(start_s), parse_date(end_s)
    except ValueError:
        return jsonify({"detail": "Dates must use YYYY-MM-DD."}), 400
    if start >= end:
        return jsonify({"detail": "End date must be after start date."}), 400
    results = []
    for doc in db.collection(UNITS).order_by("asset_tag").stream():
        data = doc.to_dict() or {}
        if data.get("status") == "maintenance":
            continue
        unit = unit_payload(doc)
        if category and unit["equipment_type"]["category"] != category:
            continue
        if not overlap(doc.id, start, end):
            results.append(unit)
    return jsonify(results)


@app.post("/api/bookings/")
@app.post("/api/bookings")
@login_required
def create_booking():
    user = current_user()
    data = body()
    try:
        unit_id = str(data.get("equipment_unit") or data.get("unit_id"))
        start = parse_date(data["start_date"])
        due = parse_date(data["due_date"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"detail": "equipment_unit, start_date and due_date are required."}), 400
    if not unit_id or unit_id == "None":
        return jsonify({"detail": "Choose an equipment unit."}), 400
    if start < date.today():
        return jsonify({"detail": "Start date cannot be in the past."}), 400
    if due <= start or (due - start).days > MAX_LOAN_DAYS:
        return jsonify({"detail": f"Booking must be 1 to {MAX_LOAN_DAYS} days."}), 400
    if active_count(user["uid"]) >= MAX_CONCURRENT_BOOKINGS:
        return jsonify({"detail": f"You already have {MAX_CONCURRENT_BOOKINGS} active bookings."}), 400
    unit_ref = db.collection(UNITS).document(unit_id)
    unit_snap = unit_ref.get()
    if not unit_snap.exists:
        return jsonify({"detail": "Equipment unit not found."}), 404
    unit_data = unit_snap.to_dict() or {}
    if unit_data.get("status") == "maintenance" or overlap(unit_id, start, due):
        return jsonify({"detail": "That equipment unit is not available for those dates."}), 400
    type_snap = db.collection(TYPES).document(unit_data["type_id"]).get()
    if not type_snap.exists:
        return jsonify({"detail": "Equipment type is missing."}), 400
    type_data = type_snap.to_dict() or {}
    booking_id = db.collection(BOOKINGS).document().id
    booking = {
        "unit_id": unit_id,
        "borrower_id": user["uid"],
        "start_date": start.isoformat(),
        "due_date": due.isoformat(),
        "returned_date": None,
        "deposit_charged": float(type_data.get("deposit_amount", 0)),
        "late_fee_charged": 0,
        "status": "reserved",
        "created_at": now_iso(),
    }
    db.collection(BOOKINGS).document(booking_id).set(booking)
    return jsonify(booking_payload(db.collection(BOOKINGS).document(booking_id).get())), 201


@app.get("/api/my-bookings/")
@app.get("/api/my-bookings")
@login_required
def mine():
    rows = []
    for snap in db.collection(BOOKINGS).stream():
        data = snap.to_dict() or {}
        if data.get("borrower_id") == current_user()["uid"]:
            rows.append(booking_payload(snap))
    rows.sort(key=lambda x: (x["start_date"], x["id"]), reverse=True)
    return jsonify(rows)


@app.post("/api/bookings/<booking_id>/cancel/")
@app.post("/api/bookings/<booking_id>/cancel")
@login_required
def cancel(booking_id):
    ref = db.collection(BOOKINGS).document(booking_id)
    snap = ref.get()
    user = current_user()
    if not snap.exists:
        return jsonify({"detail": "Booking not found."}), 404
    data = snap.to_dict() or {}
    if data.get("borrower_id") != user["uid"] and user.get("role") != "admin":
        return jsonify({"detail": "Booking not found."}), 404
    if data.get("status") != "reserved":
        return jsonify({"detail": "Only reserved bookings can be cancelled."}), 400
    if data.get("start_date") <= date.today().isoformat() and user.get("role") != "admin":
        return jsonify({"detail": "A booking can only be cancelled before its start date."}), 400
    ref.update({"status": "cancelled", "updated_at": now_iso()})
    return jsonify(booking_payload(ref.get()))


@app.get("/api/dashboard/")
@app.get("/api/dashboard")
@admin_required
def dashboard():
    today = date.today()
    cutoff = today + timedelta(days=2)
    rows = []
    for snap, data in active_bookings():
        due = parse_date(data["due_date"])
        if due <= cutoff:
            item = booking_payload(snap)
            item["days_overdue"] = max(0, (today - due).days)
            rows.append(item)
    rows.sort(key=lambda x: (x["due_date"], x["id"]))
    return jsonify(rows)


@app.get("/api/borrowers/")
@app.get("/api/users")
@admin_required
def borrowers():
    result = []
    for snap in db.collection(USERS).stream():
        data = snap.to_dict() or {}
        if data.get("is_active", True) and data.get("role") == "student":
            data["uid"] = snap.id
            result.append(user_payload(data))
    return jsonify(sorted(result, key=lambda x: x["name"].lower()))


@app.get("/api/admins/")
@admin_required
def list_admins():
    result = []
    for snap in db.collection(USERS).stream():
        data = snap.to_dict() or {}
        if data.get("is_active", True) and data.get("role") == "admin":
            data["uid"] = snap.id
            result.append(user_payload(data))
    return jsonify(sorted(result, key=lambda x: x["name"].lower()))


@app.post("/api/admins/")
@admin_required
def admins():
    data = body()
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))
    name = str(data.get("name", data.get("full_name", ""))).strip()
    email = str(data.get("email", "")).strip().lower() or None
    if not username or not password or not name:
        return jsonify({"detail": "Name, username and password are required."}), 400
    if len(password) < 8:
        return jsonify({"detail": "Admin password must be at least 8 characters."}), 400
    existing = list(firebase_auth.get_users().users)
    for u in existing:
        if u.email and email and u.email.lower() == email:
            return jsonify({"detail": "That email is already registered."}), 400
    username_docs = list(db.collection(USERS).where("username", "==", username).limit(1).stream())
    if username_docs:
        return jsonify({"detail": "That username is already taken."}), 400
    fb_user = firebase_auth.create_user(email=email, password=password, display_name=name) if email else firebase_auth.create_user(password=password, display_name=name)
    firebase_auth.set_custom_user_claims(fb_user.uid, {"admin": True})
    db.collection(USERS).document(fb_user.uid).set({"username": username, "full_name": name, "email": email, "role": "admin", "is_active": True, "created_at": now_iso(), "updated_at": now_iso()})
    return jsonify({"id": fb_user.uid, "username": username, "name": name, "email": email, "role": "admin", "is_staff": True, "is_superuser": True}), 201


@app.post("/api/bookings/<booking_id>/checkout/")
@app.post("/api/bookings/<booking_id>/checkout")
@admin_required
def checkout(booking_id):
    ref = db.collection(BOOKINGS).document(booking_id)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"detail": "Booking not found."}), 404
    data = snap.to_dict() or {}
    if data.get("status") != "reserved":
        return jsonify({"detail": "Only a reserved booking can be checked out."}), 400
    ref.update({"status": "checked_out", "updated_at": now_iso()})
    db.collection(UNITS).document(data["unit_id"]).update({"status": "checked_out", "updated_at": now_iso()})
    return jsonify(booking_payload(ref.get()))


@app.post("/api/bookings/<booking_id>/return/")
@app.post("/api/bookings/<booking_id>/return")
@admin_required
def return_item(booking_id):
    ref = db.collection(BOOKINGS).document(booking_id)
    snap = ref.get()
    if not snap.exists:
        return jsonify({"detail": "Booking not found."}), 404
    data = snap.to_dict() or {}
    if data.get("status") != "checked_out":
        return jsonify({"detail": "Only a checked-out booking can be returned."}), 400
    today = date.today()
    late = max(0, (today - parse_date(data["due_date"])).days)
    unit_snap = db.collection(UNITS).document(data["unit_id"]).get()
    unit_data = unit_snap.to_dict() or {}
    type_data = db.collection(TYPES).document(unit_data["type_id"]).get().to_dict() or {}
    fee = min(late * float(type_data.get("daily_late_fee", 0)), float(data.get("deposit_charged", 0)))
    ref.update({"returned_date": today.isoformat(), "late_fee_charged": fee, "status": "returned", "updated_at": now_iso()})
    db.collection(UNITS).document(data["unit_id"]).update({"status": "available", "updated_at": now_iso()})
    result = booking_payload(ref.get())
    result.update({"late_fee": fee, "late_days": late})
    return jsonify(result)


@app.post("/api/bookings/<booking_id>/transfer/")
@app.post("/api/bookings/<booking_id>/transfer")
@admin_required
def transfer(booking_id):
    ref = db.collection(BOOKINGS).document(booking_id)
    snap = ref.get()
    data = body()
    if not snap.exists:
        return jsonify({"detail": "Booking not found."}), 404
    booking = snap.to_dict() or {}
    target_id = str(data.get("new_borrower_id", ""))
    target_snap = db.collection(USERS).document(target_id).get()
    if not target_snap.exists:
        return jsonify({"detail": "Select a valid new borrower."}), 400
    target = target_snap.to_dict() or {}
    if not target.get("is_active", True) or target.get("role") != "student":
        return jsonify({"detail": "Select a valid new borrower."}), 400
    if booking.get("status") != "checked_out":
        return jsonify({"detail": "Only a checked-out booking can be transferred."}), 400
    if booking.get("borrower_id") == target_id:
        return jsonify({"detail": "That user is already the borrower."}), 400
    if active_count(target_id) >= MAX_CONCURRENT_BOOKINGS:
        return jsonify({"detail": f"{target.get('full_name', 'Borrower')} already has {MAX_CONCURRENT_BOOKINGS} active bookings."}), 400
    old_id = booking["borrower_id"]
    ref.update({"borrower_id": target_id, "updated_at": now_iso()})
    log_ref = db.collection(TRANSFER_LOGS).document()
    log_ref.set({"booking_id": booking_id, "from_user_id": old_id, "to_user_id": target_id, "transferred_by_id": current_user()["uid"], "transferred_at": now_iso()})
    return jsonify({"booking": booking_payload(ref.get()), "due_date_unchanged": booking["due_date"]})


@app.errorhandler(Exception)
def handle_unexpected(error):
    app.logger.exception("Unhandled application error")
    return jsonify({"detail": "An unexpected server error occurred."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
