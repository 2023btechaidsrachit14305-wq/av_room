import os
from datetime import date, timedelta

from firebase_admin import auth as firebase_auth

from firebase_service import db

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@avroom.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "avroom2026")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")

TYPES = [
    ("Canon DSLR", "DSLR", 2000, 50, ["DSLR-01", "DSLR-02", "DSLR-03"]),
    ("Epson Projector", "Projector", 1500, 40, ["PROJ-01", "PROJ-02"]),
    ("Wireless Mic", "Mic", 500, 20, ["MIC-01", "MIC-02", "MIC-03", "MIC-04"]),
    ("Camera Tripod", "Tripod", 300, 10, ["TRI-01", "TRI-02"]),
]


def upsert_firebase_user(email, password, display_name, username, role):
    try:
        fb = firebase_auth.get_user_by_email(email)
    except firebase_auth.UserNotFoundError:
        fb = firebase_auth.create_user(email=email, password=password, display_name=display_name)
    firebase_auth.update_user(fb.uid, password=password, display_name=display_name)
    firebase_auth.set_custom_user_claims(fb.uid, {"admin": role == "admin"})
    db.collection("users").document(fb.uid).set({
        "username": username,
        "full_name": display_name,
        "email": email,
        "role": role,
        "is_active": True,
    }, merge=True)
    return fb.uid


admin_uid = upsert_firebase_user(ADMIN_EMAIL, ADMIN_PASSWORD, "AV Room Administrator", ADMIN_USERNAME, "admin")
print(f"Admin: {ADMIN_EMAIL} / configured password")

for name, category, deposit, late_fee, tags in TYPES:
    type_id = category.lower()
    db.collection("equipment_types").document(type_id).set({
        "name": name,
        "category": category,
        "deposit_amount": deposit,
        "daily_late_fee": late_fee,
    }, merge=True)
    for tag in tags:
        existing = list(db.collection("equipment_units").where("asset_tag", "==", tag).limit(1).stream())
        if not existing:
            db.collection("equipment_units").add({"type_id": type_id, "asset_tag": tag, "status": "available"})

for number in range(1, 4):
    email = f"demo_student{number}@avroom.local"
    uid = upsert_firebase_user(email, "demo12345", f"Demo Student {number}", f"demo_student{number}", "student")
    if number == 1:
        unit_docs = list(db.collection("equipment_units").where("asset_tag", "==", "DSLR-01").limit(1).stream())
        if unit_docs:
            exists = list(db.collection("bookings").where("borrower_id", "==", uid).where("status", "==", "checked_out").limit(1).stream())
            if not exists:
                db.collection("bookings").add({
                    "unit_id": unit_docs[0].id,
                    "borrower_id": uid,
                    "start_date": (date.today() - timedelta(days=2)).isoformat(),
                    "due_date": (date.today() - timedelta(days=1)).isoformat(),
                    "returned_date": None,
                    "deposit_charged": 2000,
                    "late_fee_charged": 0,
                    "status": "checked_out",
                })
                unit_docs[0].reference.update({"status": "checked_out"})

print(f"Firebase seed complete. Admin UID: {admin_uid}")
print("Demo student password: demo12345")
