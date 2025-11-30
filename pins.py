from flask import Blueprint, request, jsonify
from extensions import db

bp = Blueprint("pins", __name__)

# -------------------------
# Model
# -------------------------
class SubmissionPin(db.Model):
    __tablename__ = "submission_pin"  # keep simple / legacy-friendly
    id = db.Column(db.Integer, primary_key=True)
    pin = db.Column(db.String(32), unique=True, nullable=False)
    class_id = db.Column(db.String(10), nullable=False)
    assignment_id = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.Integer, nullable=False)


# -------------------------
# Helpers
# -------------------------
def make_pin(class_id, assignment_id, student_id):
    """
    Build a PIN from:
      - class_id: 4-digit string like "3880"
      - assignment_id: int
      - student_id: int (can be 0 if not used yet)

    Result looks like: "3880" + "01" + "00" = "38800100"
    """
    cls = str(class_id).zfill(4)       # ensure 4 digits
    aid = str(assignment_id).zfill(2)  # 2 digits
    sid = str(student_id).zfill(2)     # 2 digits
    return f"{cls}{aid}{sid}"


# -------------------------
# Routes
# -------------------------
@bp.post("/api/pins")
def create_pin():
    data = request.get_json(silent=True) or {}

    class_id = data.get("class_id")
    assignment_id = data.get("assignment_id")
    # optional for now – default to 0 if you’re not using per-student pins yet
    student_id = data.get("student_id", 0)

    if class_id is None or assignment_id is None:
        return jsonify({"error": "class_id and assignment_id are required"}), 400

    pin = make_pin(class_id, assignment_id, student_id)

    existing = SubmissionPin.query.filter_by(pin=pin).first()
    if existing:
        return jsonify({"pin": existing.pin}), 200

    new_pin = SubmissionPin(
        pin=pin,
        class_id=str(class_id),
        assignment_id=int(assignment_id),
        student_id=int(student_id),
    )
    db.session.add(new_pin)
    db.session.commit()

    return jsonify({"pin": new_pin.pin}), 201


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
