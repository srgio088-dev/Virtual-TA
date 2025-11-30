from flask import Blueprint, request, jsonify, current_app
from extensions import db

bp = Blueprint("pins", __name__)


# =========================
# Model
# =========================
class SubmissionPin(db.Model):
    __tablename__ = "submission_pin"  # keep simple
    id = db.Column(db.Integer, primary_key=True)
    pin = db.Column(db.String(32), unique=True, nullable=False)
    class_id = db.Column(db.String(10), nullable=False)
    assignment_id = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.Integer, nullable=False, default=0)


# =========================
# Helper
# =========================
def make_pin(class_id, assignment_id, student_id):
    """
    Build a PIN from:
      - class_id: 4-digit string like "3880"
      - assignment_id: int
      - student_id: int (0 if not using per-student yet)

    Example: "3880" + "01" + "00" => "38800100"
    """
    cls = str(class_id).zfill(4)          # 4 digits (e.g., 3880)
    aid = f"{int(assignment_id):02d}"     # 2 digits (01, 02, 10, ...)
    sid = f"{int(student_id):02d}"        # 2 digits
    return f"{cls}{aid}{sid}"


# =========================
# Routes
# =========================
@bp.post("/api/pins")
def create_pin():
    """
    Create a PIN for a given class_id + assignment_id (+ optional student_id).

    This version is VERY forgiving:
      - Tries JSON first, then falls back to form data.
      - Defaults assignment_id / student_id to 0 if missing or invalid.
      - Defaults class_id to "0000" if missing.
      - Never returns 400 just because the payload is slightly off.
    """
    # Try to read JSON without exploding
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    # Fallback to form data if no JSON
    if not data and request.form:
        data = request.form.to_dict()

    # Pull values out, but be forgiving
    class_id = (data.get("class_id") or "").strip()
    assignment_id_raw = data.get("assignment_id")
    student_id_raw = data.get("student_id", 0)

    # Try to coerce to ints; if that fails, just default to 0
    try:
        assignment_id = int(assignment_id_raw) if assignment_id_raw is not None else 0
    except (TypeError, ValueError):
        assignment_id = 0

    try:
        student_id = int(student_id_raw) if student_id_raw is not None else 0
    except (TypeError, ValueError):
        student_id = 0

    # If class_id is blank, still generate *something*
    if not class_id:
        class_id = "0000"

    # Build the PIN string
    pin = make_pin(class_id, assignment_id, student_id)

    try:
        # Reuse existing PIN if it already exists
        existing = SubmissionPin.query.filter_by(pin=pin).first()
        if existing:
            return jsonify({"pin": existing.pin}), 200

        new_pin = SubmissionPin(
            pin=pin,
            class_id=class_id,
            assignment_id=assignment_id,
            student_id=student_id,
        )
        db.session.add(new_pin)
        db.session.commit()
        return jsonify({"pin": new_pin.pin}), 201

    except Exception as e:
        # If DB save fails, log it but STILL return the PIN so the UI works
        current_app.logger.exception("Failed to save PIN")
        return jsonify({
            "pin": pin,
            "warning": "PIN generated but not saved to DB.",
            "detail": str(e),
        }), 200


@bp.get("/api/pins/<pin>")
def resolve_pin(pin):
    row = SubmissionPin.query.filter_by(pin=pin).first()
    if not row:
        return jsonify({"error": "Invalid PIN"}), 404

    return jsonify({
        "class_id": row.class_id,
        "assignment_id": row.assignment_id,
        "student_id": row.student_id,
    })
