import os
from datetime import date, timedelta
from functools import wraps
from flask import Flask, jsonify, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///av_room.db").replace("postgres://", "postgresql://"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
db = SQLAlchemy(app)
MAX_CONCURRENT_BOOKINGS = int(os.environ.get("MAX_CONCURRENT_BOOKINGS", "3"))
MAX_LOAN_DAYS = int(os.environ.get("MAX_LOAN_DAYS", "14"))
ACTIVE_STATUSES = ("reserved", "checked_out")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    def verify(self, password): return check_password_hash(self.password_hash, password)
    def to_dict(self): return {"id": self.id, "username": self.username, "name": self.full_name, "email": self.email, "role": self.role, "is_staff": self.role == "admin"}

class EquipmentType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(30), nullable=False, index=True)
    deposit_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    daily_late_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    def to_dict(self): return {"id": self.id, "name": self.name, "category": self.category, "deposit_amount": float(self.deposit_amount or 0), "daily_late_fee": float(self.daily_late_fee or 0)}

class EquipmentUnit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type_id = db.Column(db.Integer, db.ForeignKey("equipment_type.id"), nullable=False)
    asset_tag = db.Column(db.String(50), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="available")
    equipment_type = db.relationship("EquipmentType", backref="units")
    def to_dict(self): return {"id": self.id, "asset_tag": self.asset_tag, "status": self.status, "equipment_type": self.equipment_type.to_dict()}

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("equipment_unit.id"), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False, index=True)
    due_date = db.Column(db.Date, nullable=False, index=True)
    returned_date = db.Column(db.Date)
    deposit_charged = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    late_fee_charged = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="reserved", index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    unit = db.relationship("EquipmentUnit", backref="bookings")
    borrower = db.relationship("User", backref="bookings")
    def to_dict(self):
        return {"id": self.id, "borrower": self.borrower.to_dict(), "borrower_id": self.borrower_id,
                "equipment_unit": {"id": self.unit.id, "asset_tag": self.unit.asset_tag, "status": self.unit.status, "name": self.unit.equipment_type.name, "category": self.unit.equipment_type.category},
                "start_date": self.start_date.isoformat(), "due_date": self.due_date.isoformat(),
                "returned_date": self.returned_date.isoformat() if self.returned_date else None,
                "deposit_charged": float(self.deposit_charged or 0), "late_fee_charged": float(self.late_fee_charged or 0),
                "refund_amount": float((self.deposit_charged or 0) - (self.late_fee_charged or 0)), "status": self.status}

class TransferLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    transferred_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    transferred_at = db.Column(db.DateTime, server_default=db.func.now())

def current_user(): return db.session.get(User, session.get("user_id")) if session.get("user_id") else None

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u=current_user()
        if not u or not u.is_active: return jsonify({"detail":"Authentication required."}),401
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u=current_user()
        if not u or not u.is_active: return jsonify({"detail":"Authentication required."}),401
        if u.role!="admin": return jsonify({"detail":"Admin access required."}),403
        return f(*args, **kwargs)
    return wrapper

def data(): return request.get_json(silent=True) or {}
def active_count(uid): return Booking.query.filter(Booking.borrower_id==uid,Booking.status.in_(ACTIVE_STATUSES)).count()
def overlap(unit_id,start,end): return Booking.query.filter(Booking.unit_id==unit_id,Booking.status.in_(ACTIVE_STATUSES),Booking.start_date<end,Booking.due_date>start).first() is not None
def user_payload(u): return {"id":u.id,"username":u.username,"name":u.full_name,"email":u.email,"role":u.role,"is_staff":u.role=="admin","is_superuser":u.role=="admin"}

@app.get("/")
def home(): return app.send_static_file("index.html")

@app.get("/api/auth/me/")
@app.get("/api/me")
def me():
    u=current_user();ok=bool(u and u.is_active);return jsonify({"authenticated":ok,"user":user_payload(u) if ok else None})

@app.post("/api/auth/login/")
@app.post("/api/login")
def login():
    d=data();u=User.query.filter_by(username=str(d.get("username","")).strip().lower()).first();p=str(d.get("password",""))
    if not u or not u.is_active or not u.verify(p):return jsonify({"detail":"Invalid username or password."}),401
    session.clear();session["user_id"]=u.id;return jsonify({"authenticated":True,"user":user_payload(u)})

@app.post("/api/auth/register/")
@app.post("/api/register")
def register():
    d=data();username=str(d.get("username","")).strip().lower();password=str(d.get("password",""));first=str(d.get("first_name","")).strip();last=str(d.get("last_name","")).strip();email=str(d.get("email","")).strip().lower() or None
    if not username or not first or not password:return jsonify({"detail":"First name, username and password are required."}),400
    if len(password)<8:return jsonify({"detail":"Password must be at least 8 characters."}),400
    if User.query.filter_by(username=username).first():return jsonify({"detail":"That username is already taken."}),400
    if email and User.query.filter_by(email=email).first():return jsonify({"detail":"That email is already registered."}),400
    u=User(username=username,full_name=f"{first} {last}".strip(),email=email,password_hash=generate_password_hash(password),role="student");db.session.add(u);db.session.commit();session.clear();session["user_id"]=u.id
    return jsonify({"authenticated":True,"user":user_payload(u)}),201

@app.post("/api/auth/logout/")
@app.post("/api/logout")
def logout():session.clear();return jsonify({"authenticated":False})

@app.get("/api/equipment-types")
def equipment_types():return jsonify([t.to_dict() for t in EquipmentType.query.order_by(EquipmentType.category,EquipmentType.name).all()])

@app.get("/api/availability/")
@app.get("/api/availability")
def availability():
    category=request.args.get("category","").strip();start_s=request.args.get("start_date") or request.args.get("start");end_s=request.args.get("end_date") or request.args.get("end")
    if not start_s or not end_s:return jsonify({"detail":"Start date and end date are required."}),400
    try:start=date.fromisoformat(start_s);end=date.fromisoformat(end_s)
    except ValueError:return jsonify({"detail":"Dates must use YYYY-MM-DD."}),400
    if start>=end:return jsonify({"detail":"End date must be after start date."}),400
    q=EquipmentUnit.query.join(EquipmentType).filter(EquipmentUnit.status!="maintenance")
    if category:q=q.filter(EquipmentType.category==category)
    return jsonify([u.to_dict() for u in q.order_by(EquipmentUnit.asset_tag).all() if not overlap(u.id,start,end)])

@app.post("/api/bookings/")
@app.post("/api/bookings")
@login_required
def create_booking():
    u=current_user();d=data()
    try:unit_id=int(d.get("equipment_unit",d.get("unit_id")));start=date.fromisoformat(d["start_date"]);due=date.fromisoformat(d["due_date"])
    except(TypeError,ValueError,KeyError):return jsonify({"detail":"equipment_unit, start_date and due_date are required."}),400
    if start<date.today():return jsonify({"detail":"Start date cannot be in the past."}),400
    if due<=start or(due-start).days>MAX_LOAN_DAYS:return jsonify({"detail":f"Booking must be 1 to {MAX_LOAN_DAYS} days."}),400
    if active_count(u.id)>=MAX_CONCURRENT_BOOKINGS:return jsonify({"detail":f"You already have {MAX_CONCURRENT_BOOKINGS} active bookings."}),400
    unit=db.session.get(EquipmentUnit,unit_id)
    if not unit or unit.status=="maintenance" or overlap(unit.id,start,due):return jsonify({"detail":"That equipment unit is not available for those dates."}),400
    b=Booking(unit=unit,borrower=u,start_date=start,due_date=due,deposit_charged=unit.equipment_type.deposit_amount,status="reserved");db.session.add(b);db.session.commit();return jsonify(b.to_dict()),201

@app.get("/api/my-bookings/")
@app.get("/api/my-bookings")
@login_required
def mine():return jsonify([b.to_dict() for b in Booking.query.filter_by(borrower_id=current_user().id).order_by(Booking.start_date.desc(),Booking.id.desc()).all()])

@app.post("/api/bookings/<int:booking_id>/cancel/")
@app.post("/api/bookings/<int:booking_id>/cancel")
@login_required
def cancel(booking_id):
    b=db.session.get(Booking,booking_id);u=current_user()
    if not b or(b.borrower_id!=u.id and u.role!="admin"):return jsonify({"detail":"Booking not found."}),404
    if b.status!="reserved":return jsonify({"detail":"Only reserved bookings can be cancelled."}),400
    if b.start_date<=date.today() and u.role!="admin":return jsonify({"detail":"A booking can only be cancelled before its start date."}),400
    b.status="cancelled";db.session.commit();return jsonify(b.to_dict())

@app.get("/api/dashboard/")
@app.get("/api/dashboard")
@admin_required
def dashboard():
    today=date.today();cutoff=today+timedelta(days=2);rows=Booking.query.filter(Booking.status.in_(("reserved","checked_out")),Booking.due_date<=cutoff).order_by(Booking.due_date,Booking.id).all();return jsonify([{**b.to_dict(),"days_overdue":max(0,(today-b.due_date).days)} for b in rows])

@app.get("/api/borrowers/")
@app.get("/api/users")
@admin_required
def borrowers():return jsonify([user_payload(u) for u in User.query.filter_by(is_active=True,role="student").order_by(User.full_name).all()])

@app.get("/api/admins/")
@admin_required
def list_admins():return jsonify([user_payload(u) for u in User.query.filter_by(is_active=True,role="admin").order_by(User.full_name).all()])

@app.post("/api/admins/")
@admin_required
def admins():
    d=data();username=str(d.get("username","")).strip().lower();password=str(d.get("password",""));name=str(d.get("name",d.get("full_name",""))).strip();email=str(d.get("email","")).strip().lower() or None
    if not username or not password or not name:return jsonify({"detail":"Name, username and password are required."}),400
    if len(password)<8:return jsonify({"detail":"Admin password must be at least 8 characters."}),400
    if User.query.filter_by(username=username).first():return jsonify({"detail":"That username is already taken."}),400
    u=User(username=username,full_name=name,email=email,password_hash=generate_password_hash(password),role="admin");db.session.add(u);db.session.commit();return jsonify(user_payload(u)),201

@app.post("/api/bookings/<int:booking_id>/checkout/")
@app.post("/api/bookings/<int:booking_id>/checkout")
@admin_required
def checkout(booking_id):
    b=db.session.get(Booking,booking_id)
    if not b:return jsonify({"detail":"Booking not found."}),404
    if b.status!="reserved":return jsonify({"detail":"Only a reserved booking can be checked out."}),400
    b.status="checked_out";b.unit.status="checked_out";db.session.commit();return jsonify(b.to_dict())

@app.post("/api/bookings/<int:booking_id>/return/")
@app.post("/api/bookings/<int:booking_id>/return")
@admin_required
def return_item(booking_id):
    b=db.session.get(Booking,booking_id)
    if not b:return jsonify({"detail":"Booking not found."}),404
    if b.status!="checked_out":return jsonify({"detail":"Only a checked-out booking can be returned."}),400
    today=date.today();late=max(0,(today-b.due_date).days);fee=min(late*float(b.unit.equipment_type.daily_late_fee),float(b.deposit_charged));b.returned_date=today;b.late_fee_charged=fee;b.status="returned";b.unit.status="available";db.session.commit();r=b.to_dict();r["late_fee"]=fee;r["late_days"]=late;return jsonify(r)

@app.post("/api/bookings/<int:booking_id>/transfer/")
@app.post("/api/bookings/<int:booking_id>/transfer")
@admin_required
def transfer(booking_id):
    b=db.session.get(Booking,booking_id);d=data()
    try:target=db.session.get(User,int(d.get("new_borrower_id")))
    except(TypeError,ValueError):target=None
    if not b:return jsonify({"detail":"Booking not found."}),404
    if not target or not target.is_active or target.role!="student":return jsonify({"detail":"Select a valid new borrower."}),400
    if b.status!="checked_out":return jsonify({"detail":"Only a checked-out booking can be transferred."}),400
    if b.borrower_id==target.id:return jsonify({"detail":"That user is already the borrower."}),400
    if active_count(target.id)>=MAX_CONCURRENT_BOOKINGS:return jsonify({"detail":f"{target.full_name} already has {MAX_CONCURRENT_BOOKINGS} active bookings."}),400
    old=b.borrower_id;b.borrower_id=target.id;db.session.add(TransferLog(booking_id=b.id,from_user_id=old,to_user_id=target.id,transferred_by_id=current_user().id));db.session.commit();return jsonify({"booking":b.to_dict(),"due_date_unchanged":b.due_date.isoformat()})

with app.app_context():db.create_all()
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")),debug=os.environ.get("FLASK_DEBUG","false").lower()=="true")
