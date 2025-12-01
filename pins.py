# src/pins.py
from flask import Blueprint, request, jsonify
from extensions import db
import random
import string

bp = Blueprint("pins", __name__)

# ---------- MODEL ----------

class Pin(db.Model):
    __tablename__ = "pins"  # assumes your table is named 'pins'

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, nullable=False)
    class_id = db.Column(db.Integer, nullable=True)
    pin_code = db.Column(db.String(32), unique=True, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "class_id": self.class_id,
            "pin_code": self.pin_code,
        }


# ---------- HELPERS ----------

def generate_pin_code(length: int = 6) -> str:
    """
    Generate a random numeric PIN code, e.g. '483920'.
    """
    digits = string.digits  # "0123456789"
    return "".join(random.choice(digits) for _ in range(length))


# ---------- ROUTES ----------

@bp.route("/api/pins", methods=["POST"])
def create_pin():
    """
    Create a new PIN for an assignment.

    Current frontend (AssignmentList.jsx) sends JSON like:
    {
      "class_id": 4850,
      "assignment_id": 2
    }

    This endpoint:
    - Validates assignment_id (required, int)
    - Validates class_id (optional, int if present)
    - Auto-generates a 6-digit numeric pin_code if none provided
    - Returns: { id, assignment_id, class_id, pin_code }
    """
    data = request.get_json(silent=True) or {}

    # Debug if needed:
    # print("DEBUG /api/pins payload:", data, flush=True)

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
    if raw_class_id not in (None, "", []):
        try:
            class_id = int(raw_class_id)
        except (TypeError, ValueError):
            return jsonify({"error": "class_id must be an integer if provided"}), 400

    # --- pin_code: optional string; auto-generate if missing ---
    raw_pin_code = data.get("pin_code") or data.get("pinCode")
    if raw_pin_code:
        pin_code = str(raw_pin_code).strip()
    else:
        # Auto-generate a unique 6-digit numeric PIN
        pin_code = generate_pin_code()
        while Pin.query.filter_by(pin_code=pin_code).first() is not None:
            pin_code = generate_pin_code()

    # --- create and save Pin ---
    pin = Pin(
        assignment_id=assignment_id,
        class_id=class_id,
        pin_code=pin_code,
    )

    try:
        db.session.add(pin)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Log the full error on the server
        print("ERROR creating PIN:", e, flush=True)
        return jsonify({"error": "Internal error creating PIN"}), 500

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
