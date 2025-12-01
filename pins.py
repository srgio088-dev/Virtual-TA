# pins.py

from flask import Blueprint, request, jsonify
from app import db  # <- change this if your other files import db differently
from models import Pin  # assumes Pin model is defined in models.py

bp = Blueprint("pins", __name__)

def pin_to_dict(pin):
    """Safe serializer for Pin objects."""
    return {
        "id": getattr(pin, "id", None),
        "assignment_id": getattr(pin, "assignment_id", None),
        "class_id": getattr(pin, "class_id", None),
        "pin_code": getattr(pin, "pin_code", None),
    }


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

    # --- create and save Pin ---
    pin = Pin(
        assignment_id=assignment_id,
        class_id=class_id,
        pin_code=pin_code,
    )

    db.session.add(pin)
    db.session.commit()

    return jsonify(pin_to_dict(pin)), 201


@bp.route("/api/pins/<string:pin_code>", methods=["GET"])
def get_pin_by_code(pin_code):
    """
    Look up a pin by its code.

    Used by the student PIN entry flow if you want to fetch the assignment via PIN.
    """
    pin = Pin.query.filter_by(pin_code=pin_code).first()
    if not pin:
        return jsonify({"error": "PIN not found"}), 404

    return jsonify(pin_to_dict(pin)), 200
