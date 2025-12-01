# pins.py

from flask import Blueprint, request, jsonify
from extensions import db  # same place app.py gets db from
import random
import string

bp = Blueprint("pins", __name__)

# ---------- MODEL ----------

class Pin(db.Model):
    __tablename__ = "pins"  # matches your existing table name

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, nullable=False)
    class_id = db.Column(db.Integer, nullable=True)
    pin_code = db.Column(db.String(32), unique=True, nullable=False)
    # NOTE: your current DB table doesn't have student_id, so we are NOT storing it yet.

    def to_dict(self):
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "class_id": self.class_id,
            "pin_code": self.pin_code,
        }


# ---------- HELPERS ----------

def generate_pin_code(length: int = 6) -> str:
    """Generate a random alphanumeric PIN code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


# ---------- ROUTES ----------

@bp.route("/api/pins", methods=["POST"])
def create_pin():
    """
    Create a new PIN for an assignment.

    Frontend is currently sending JSON like:
    {
      "class_id": 4850,
      "assignment_id": 2,
      "student_id": "Jed Cooper"
    }

    This endpoint will:
    - Read assignment_id and class_id
    - Ignore student_id for now (DB schema doesn't have it yet)
    - Auto-generate a pin_code if one is not provided
    """
    data = request.get_json() or {}

    # print("DEBUG /api/pins data:", data, flush=True)  # uncomment if you want to see payload in logs

    # --- assignment_id: required, must be an integer ---
    raw_assignment_id = data.get("assignment_id") or data.get("assignmentId")
    if raw_assignment_id is None:
        return jsonify({"error": "assignment_id (or assignmentId) is required"}), 400

    try:
        assignment_id = int(raw_assignment_id)
    except (TypeError, ValueError):
        return jsonify({"error": "assignment_id must be an integer"}), 400

    # --- class_id: optional, integer if provided ---
    raw_class_id = data.get("class_id") or data.get("classId")
    class_id = None
    if raw_class_id not in (None, ""):
        try:
            class_id = int(raw_class_id)
        except (TypeError, ValueError):
            return jsonify({"error": "class_id must be an integer if provided"}), 400

    # --- student_id: currently ignored (no column yet), but we accept it ---
    student_id = data.get("student_id") or data.get("studentId")
    # You can log it if you want:
    # print("DEBUG student_id:", student_id, flush=True)

    # --- pin_code: optional string; auto-generate if missing ---
    raw_pin_code = data.get("pin_code") or data.get("pinCode")
    if raw_pin_code:
        pin_code = str(raw_pin_code).strip()
    else:
        # Auto-generate a unique PIN
        pin_code = generate_pin_code()
        # Ensure uniqueness
        while Pin.query.filter_by(pin_code=pin_code).first() is not None:
            pin_code = generate_pin_code()

    # --- create and save Pin ---
    pin = Pin(
        assignment_id=assignment_id,
        class_id=class_id,
        pin_code=pin_code,
    )

    db.session.add(pin)
    db.session.commit()

    return jsonify(pin.to_dict()), 201


@bp.route("/api/pins/<string:pin_code>", methods=["GET"])
def get_pin_by_code(pin_code):
    """
    Look up a pin by its code.

    Used by the student PIN entry flow to find the assignment via PIN.
    """
    pin = Pin.query.filter_by(pin_code=pin_code).first()
    if not pin:
        return jsonify({"error": "PIN not found"}), 404

    return jsonify(pin.to_dict()), 200
