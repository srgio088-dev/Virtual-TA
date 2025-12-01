from flask import Blueprint, request, jsonify
from models import db, Pin  # adjust import if needed

pins_bp = Blueprint("pins", __name__)

@pins_bp.route("/api/pins", methods=["POST"])
def create_pin():
    data = request.get_json() or {}

    # assignment_id: required, must be an integer
    raw_assignment_id = data.get("assignment_id")
    try:
        assignment_id = int(raw_assignment_id)
    except (TypeError, ValueError):
        return jsonify({"error": "assignment_id is required and must be an integer"}), 400

    # class_id: optional, integer if provided
    raw_class_id = data.get("class_id")
    class_id = None
    if raw_class_id not in (None, ""):
        try:
            class_id = int(raw_class_id)
        except (TypeError, ValueError):
            return jsonify({"error": "class_id must be an integer if provided"}), 400

    # pin_code: required string
    pin_code = (data.get("pin_code") or "").strip()
    if not pin_code:
        return jsonify({"error": "pin_code is required"}), 400

    # Create and save the pin
    pin = Pin(
        assignment_id=assignment_id,
        class_id=class_id,
        pin_code=pin_code,
    )
    db.session.add(pin)
    db.session.commit()

    # Return something the frontend can use
    return jsonify(pin.to_dict() if hasattr(pin, "to_dict") else {
        "id": pin.id,
        "assignment_id": pin.assignment_id,
        "class_id": pin.class_id,
        "pin_code": pin.pin_code,
    }), 201
