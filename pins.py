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
    # Parse JSON safely
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    class_id = str(data.get("class_id", "")).strip()
    assignment_id = data.get("assignment_id")
    student_id = data.get("student_id", 0)

    # Basic validation
    if not class_id or assignment_id is None:
        return jsonify({"error": "class_id and assignment_id are required"}), 400

    try:
        assignment_id = int(assignment_id)
        student_id = int(student_id)
    except ValueError:
        return jsonify({"error": "assignment_id and student_id must be integers"}), 400

    # Build the PIN string
    pin = make_pin(class_id, assignment_id, student_id)

    # Try to save / reuse without crashing
    try:
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
        # Log the error but still return the pin so the UI keeps working
        current_app.logger.exception("Failed to save PIN in database")
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
