import os
from werkzeug.security import generate_password_hash
from app import app, db, User, EquipmentType, EquipmentUnit

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "avroom2026")

TYPES = [
    ("Canon DSLR", "DSLR", 2000, 50, ["DSLR-01", "DSLR-02", "DSLR-03"]),
    ("Epson Projector", "Projector", 1500, 40, ["PROJ-01", "PROJ-02"]),
    ("Wireless Mic", "Mic", 500, 20, ["MIC-01", "MIC-02", "MIC-03", "MIC-04"]),
    ("Camera Tripod", "Tripod", 300, 10, ["TRI-01", "TRI-02"]),
]

with app.app_context():
    db.create_all()
    admin = User.query.filter_by(username=ADMIN_USERNAME).first()
    if not admin:
        admin = User(username=ADMIN_USERNAME, full_name="AV Room Administrator", password_hash=generate_password_hash(ADMIN_PASSWORD), role="admin")
        db.session.add(admin)
    elif admin.role != "admin":
        admin.role = "admin"
    db.session.commit()

    for name, category, deposit, fee, tags in TYPES:
        et = EquipmentType.query.filter_by(name=name).first()
        if not et:
            et = EquipmentType(name=name, category=category, deposit_amount=deposit, daily_late_fee=fee)
            db.session.add(et)
            db.session.flush()
        for tag in tags:
            if not EquipmentUnit.query.filter_by(asset_tag=tag).first():
                db.session.add(EquipmentUnit(equipment_type=et, asset_tag=tag, status="available"))
    db.session.commit()

    demos = [("demo_student1", "Demo Student One"), ("demo_student2", "Demo Student Two"), ("demo_student3", "Demo Student Three")]
    for username, name in demos:
        if not User.query.filter_by(username=username).first():
            db.session.add(User(username=username, full_name=name, password_hash=generate_password_hash("demo12345"), role="student"))
    db.session.commit()

print("AV Room seed complete.")
print(f"Admin username: {ADMIN_USERNAME}")
print("Admin password: value of ADMIN_PASSWORD (default: avroom2026)")
print("Demo student password: demo12345")
