# pins.py

from flask import Blueprint, request, jsonify
from extensions import db  # same place app.py gets db from

bp = Blueprint("pins", __name__)

# ---------- MODEL ----------

class Pin(db.Model):
    __tablename__ = "pins"  # change if you use a different naming style

    id = db.Column(db.Integer, primary_key=True)
    # Assumes you already have an Assignment model with table name "assignments" and PK "id"
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


# ---------- ROUTES ----------

@bp.route("/api/pins", methods=["POST"])
def create_pin():
    """
    Create a new PIN for an assignment.

    Expects JSON like:
    {
      "assignment_id": 3,        # required (int or string that can be cast to int)
      "pin_code": "ABC123",      # required (string)
      "class_id": 1              # optional (int or string)
    }
    """
    data = request.get_json() or {}

    # --- assignment_id: required, must be an integer ---
    raw_assignment_id = data.get("assignment_id")
    if raw_assignment_id is None:
        return jsonify({"error": "assignment_id is required"}), 400

    try:
        assignment_id = int(raw_assignment_id)
    except (TypeError, ValueError):
        return jsonify({"error": "assignment_id must be an integer"}), 400

    # --- class_id: optional, integer if provided ---
    raw_class_id = data.get("class_id")
    class_id = None
    if raw_class_id not in (None, ""):
        try:
            class_id = int(raw_class_id)
        except (TypeError, ValueError):
            return jsonify({"error": "class_id must be an integer if provided"}), 400

    # --- pin_code: required string ---
    pin_code = (data.get("pin_code") or "").strip()
    if not pin_code:
        return jsonify({"error": "pin_code is required"}), 400

    # Optional: prevent duplicate pin codes
    existing = Pin.query.filter_by(pin_code=pin_code).first()
    if existing:
        return jsonify({"error": "A PIN with this code already exists"}), 409

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
