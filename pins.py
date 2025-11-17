from flask import Blueprint, request
from app import db
from models.submission_pin import SubmissionPin

bp = Blueprint("pins", __name__)

def make_pin(class_id, assignment_id, student_id):
    return f"{class_id:02d}{assignment_id:02d}{student_id:02d}"


@bp.post("/api/pins")
def create_pin():
    data = request.json

    class_id = data["class_id"]
    assignment_id = data["assignment_id"]
    student_id = data["student_id"]

    pin = make_pin(class_id, assignment_id, student_id)

    existing = SubmissionPin.query.filter_by(pin=pin).first()
    if existing:
        return {"pin": pin}

    new_pin = SubmissionPin(
        pin=pin,
        class_id=class_id,
        assignment_id=assignment_id,
        student_id=student_id
    )
    db.session.add(new_pin)
    db.session.commit()

    return {"pin": pin}


@bp.get("/api/pins/<pin>")
def resolve_pin(pin):
    row = SubmissionPin.query.filter_by(pin=pin).first()
    if not row:
        return {"error": "Invalid PIN"}, 404

    return {
        "class_id": row.class_id,
        "assignment_id": row.assignment_id,
        "student_id": row.student_id
    }
