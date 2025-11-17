from app import db

class SubmissionPin(db.Model):
    __tablename__ = "submission_pins"

    id = db.Column(db.Integer, primary_key=True)
    pin = db.Column(db.String(6), unique=True, nullable=False)

    class_id = db.Column(db.Integer, nullable=False)
    assignment_id = db.Column(db.Integer, nullable=False)
    student_id = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
