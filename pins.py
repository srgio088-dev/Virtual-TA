from flask import Blueprint, request, jsonify

bp = Blueprint("pins", __name__)


# =========================
# Helper
# =========================
def make_pin(class_id, assignment_id, student_id=0):
    """
    Build a PIN from:
      - class_id: 4-digit string like "3880"
      - assignment_id: int
      - student_id: int (optional, default 0)

    Example: "3880" + "01" + "00" => "38800100"
    """
    cls = str(class_id).zfill(4)              # 4 digits (e.g., 3880)
    try:
        aid = f"{int(assignment_id):02d}"     # 2 digits (01, 02, 10, ...)
    except (TypeError, ValueError):
        aid = "00"

    try:
        sid = f"{int(student_id):02d}"        # 2 digits
    except (TypeError, ValueError):
        sid = "00"

    return f"{cls}{aid}{sid}"


# =========================
# Routes
# =========================
@bp.post("/api/pins")
def create_pin():
    """
    Create a PIN for a given class_id + assignment_id (+ optional student_id).

    This version:
      - Does NOT use the database at all (no table errors, no migrations needed).
      - Tries JSON first; if that fails, falls back to form data.
      - Always returns a JSON with a 'pin' field (HTTP 200).
    """
    # Try to read JSON safely
    data = request.get_json(silent=True)
    if not data:
        # Fallback: try form data (just in case)
        data = request.form.to_dict() if request.form else {}

    class_id = (data.get("class_id") or "").strip()
    assignment_id = data.get("assignment_id")
    student_id = data.get("student_id", 0)

    # If class_id somehow missing, still produce something
    if not class_id:
        class_id = "0000"

    pin = make_pin(class_id, assignment_id, student_id)

    return jsonify({"pin": pin}), 200


@bp.get("/api/pins/<pin>")
def resolve_pin(pin):
    """
    Simple echo endpoint — in a more advanced version we could
    decode class_id / assignment_id back out from the pin string.
    For now, just return the raw pin.
    """
    return jsonify({"pin": pin}), 200
