import os, json, datetime
from pathlib import Path
from sqlalchemy import or_
from auth import require_professor
from flask import Flask, request, jsonify, send_file
from extensions import db              # ✅ shared SQLAlchemy instance
from dotenv import load_dotenv
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
from pypdf import PdfReader
from docx import Document  # python-docx
from flask_migrate import Migrate 
from filename_utils import parse_submission_filename  # Edit 12-3



# =========================
# Config
# =========================
load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "sqlite:///virtualta.db")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB

# Enable CORS for your frontend (Netlify + local dev)
CORS(
    app,
    supports_credentials=True,
    origins=os.getenv(
        "FRONTEND_ORIGINS",
        "https://virtualteacher.netlify.app"
    ).split(","),
)

# ✅ initialize db with the app (using extensions.db)
db.init_app(app)

# ✅ ADD THIS LINE (required for flask db migrate/upgrade)
migrate = Migrate(app, db)

# ✅ create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# ✅ NOW import and register the blueprint (no circular import)
from pins import bp as pins_bp
app.register_blueprint(pins_bp)

# =========================
# Models
# =========================
class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    rubric = db.Column(db.Text, nullable=True)
    # NEW: which professor owns this assignment
    owner_email = db.Column(db.String(255), nullable=True)
    rubric_id = db.Column(db.Integer, db.ForeignKey("rubric.id"), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True) #NEW 11/19
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    submissions = db.relationship(
        "Submission",
        backref="assignment",
        cascade="all, delete-orphan",
        lazy=True,
    )

class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id"), nullable=False)
    student_name = db.Column(db.String(180), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    ai_feedback = db.Column(db.Text)
    ai_grade = db.Column(db.String(20))
    final_grade = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def get_request_user_email():
        # Netlify Identity email we’re passing from the frontend
        return request.headers.get("X-User-Email")

    def to_dict_short(self):
        return {
            "id": self.id,
            "student_name": self.student_name,
            "ai_grade": self.ai_grade,
            "final_grade": self.final_grade,
            "created_at": self.created_at.isoformat(),
        }

    def to_dict_full(self):
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "student_name": self.student_name,
            "file_path": self.file_path,
            "ai_feedback": self.ai_feedback,
            "ai_grade": self.ai_grade,
            "final_grade": self.final_grade,
            "created_at": self.created_at.isoformat(),
        }

class Rubric(db.Model):
    # default __tablename__ will be "rubric" (lowercased class name)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    body = db.Column(db.Text, nullable=False)  # the rubric text

with app.app_context():
    db.create_all()

# =========================
# Helpers
# =========================
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}

def get_request_email() -> str | None:
    """
    Lightweight way to know 'who' is calling without full JWT auth.

    The frontend will send the logged-in Netlify Identity user's email
    as the X-User-Email header on each request.
    """
    return request.headers.get("X-User-Email")
    
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def assignment_to_dict(a: Assignment):
    return {
        "id": a.id,
        "name": a.name,
        "rubric": a.rubric_text,
        "rubric_id": a.rubric_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "due_date": a.due_date.isoformat() if a.due_date else None,
        "owner_email": a.owner_email,   # optional but handy for checking
        "submissions": [submission_to_dict(s) for s in a.submissions],
        "submission_count": len(a.submissions),
    }

def infer_student_name(fname: str) -> str:
    base = Path(fname).stem
    parts = base.replace("-", " ").replace(".", " ").split("_")
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return base

def extract_text(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[1].lower()
    if ext == "txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    if ext == "pdf":
        text = []
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
    if ext == "docx":
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    return ""

def extract_rubric_from_upload(file_storage):
    """
    Return plain text from an uploaded rubric file (PDF, DOCX, or TXT).
    Expects a Werkzeug FileStorage object (request.files[...] item).
    """
    if not file_storage:
        return ""

    filename = (file_storage.filename or "").lower()
    ext = os.path.splitext(filename)[1]

    # PDF -> use PdfReader
    if ext == ".pdf":
        parts = []
        reader = PdfReader(file_storage)
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n\n".join(parts).strip()

    # DOCX/DOC -> python-docx
    if ext in (".docx", ".doc"):
        doc = Document(file_storage)
        return "\n".join(p.text for p in doc.paragraphs).strip()

    # Fallback -> treat as plain text
    data = file_storage.read()
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="ignore").strip()

def get_request_email():
    """
    Get the logged-in user's email from headers or cookie.
    Frontend sends X-User-Email on every request.
    """
    email = request.headers.get("X-User-Email")
    if not email:
        email = request.cookies.get("user_email")
    return email

def grade_with_openai(submission_text: str, rubric_text: str) -> tuple[str, str]:
    """
    Returns (feedback, grade_str). On API/quota error, returns ("[AI error ...]", "Pending").
    """
    if not OPENAI_API_KEY:
        return "[AI error or parse issue] Missing OPENAI_API_KEY", "Pending"

    system = (
        "You are a fair, consistent teaching assistant. "
        "Grade student work strictly by the rubric. Be constructive and specific."
    )

    user = f"""
Rubric:
\"\"\"{rubric_text}\"\"\"


Student Submission (may be truncated):
\"\"\"{submission_text[:12000]}\"\"\"

Return a JSON object with:
- "feedback": string with concrete, actionable comments
- "grade": integer 0-100
"""
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        feedback = str(data.get("feedback", "")).strip()
        grade = str(data.get("grade", ""))
        if not grade or grade.lower() == "none":
            grade = "Pending"
        return feedback, grade
    except Exception as e:
        # e.g., 429 insufficient_quota; keep app usable
        return f"[AI error or parse issue] {e}", "Pending"

# =========================
# Routes
# =========================

# Health
@app.get("/api/health")
def health():
    return jsonify({"ok": True, "time": datetime.datetime.utcnow().isoformat()})

# ----- Rubrics -----
@app.get("/api/rubrics")
def list_rubrics():
    items = Rubric.query.order_by(Rubric.name.asc()).all()
    return jsonify([{"id": r.id, "name": r.name, "body": r.body} for r in items])

@app.post("/api/rubrics")
def create_rubric():
    data = request.get_json(force=True)
    name = (data or {}).get("name")
    body = (data or {}).get("body")
    if not name or not body:
        return jsonify({"error": "name and body are required"}), 400
    r = Rubric(name=name.strip(), body=body.strip())
    db.session.add(r)
    db.session.commit()
    return jsonify({"id": r.id, "name": r.name}), 201

@app.delete("/api/rubrics/<int:rid>")
def delete_rubric(rid):
    r = Rubric.query.get(rid)
    if not r:
        return jsonify({"error": "rubric not found"}), 404
    # prevent delete if assignments reference it (optional)
    in_use = Assignment.query.filter_by(rubric_id=rid).count()
    if in_use:
        return jsonify({"error": "rubric in use by assignments"}), 400
    db.session.delete(r)
    db.session.commit()
    return jsonify({"ok": True})

# ----- Assignments -----
@app.get("/api/assignments")
def get_assignments():
    # May be None if user is not logged in or header missing
    user_email = request.headers.get("X-User-Email")

    q = Assignment.query.order_by(Assignment.created_at.desc())

    # If we have a user, show:
    #   - assignments owned by them
    #   - plus "global" assignments with no owner_email
    if user_email:
        q = q.filter(
            or_(
                Assignment.owner_email == user_email,
                Assignment.owner_email.is_(None),
                Assignment.owner_email == ""  # just in case
            )
        )

    items = q.all()
    return jsonify([assignment_to_dict(a) for a in items])
    
@app.post("/api/assignments")
def create_assignment():
    data = request.get_json(force=True) or {}

    name = (data.get("name") or "").strip()
    rubric_text = (data.get("rubric") or "").strip() or None
    rubric_id = data.get("rubric_id")  # optional
    due_date_str = data.get("due_date")
    count = int(data.get("count") or 1)

    # NEW: current user (might be None if someone hits endpoint without login)
    owner_email = request.headers.get("X-User-Email")

    if not name or (not rubric_text and not rubric_id):
        return jsonify({"error": "name and either rubric or rubric_id are required"}), 400

    created = []

    for i in range(count):
        if count > 1:
            final_name = f"{name} {i+1}"
        else:
            final_name = name

        a = Assignment(
            name=final_name,
            rubric_text=rubric_text,
            rubric_id=rubric_id,
            owner_email=owner_email,  # <<— key line
        )

        if due_date_str:
            from datetime import datetime
            a.due_date = datetime.fromisoformat(due_date_str)

        db.session.add(a)
        created.append(a)

    db.session.commit()
    return jsonify([assignment_to_dict(a) for a in created]), 201
    
@app.get("/api/assignments/<int:aid>")
def get_assignment(aid):
    try:
        # Prefer session.get (SQLAlchemy 2.x) but fallback to query.get if needed
        a = getattr(db.session, "get", None)
        a = a(Assignment, aid) if a else Assignment.query.get(aid)

        if not a:
            return jsonify({"error": "assignment not found"}), 404

        # Be flexible about the rubric field name
        rubric_value = getattr(a, "rubric", None) or getattr(a, "rubric_text", None)

        return jsonify({
            "id": a.id,
            "name": a.name,
            "rubric": rubric_value
        })
    except Exception as e:
        # Log full stacktrace to Gunicorn error log
        app.logger.exception("GET /api/assignments/%s failed", aid)
        return jsonify({"error": "internal", "detail": str(e)}), 500
# =================================================
#    OLD CODE 11/19

#@app.patch("/api/assignments/<int:aid>")
#def update_assignment(aid):
#    a = Assignment.query.get(aid)
#    if not a:
#        return jsonify({"error": "assignment not found"}), 404
#    data = request.get_json(force=True)
#    if "name" in data:
#        a.name = (data["name"] or "").strip()
#    if "rubric" in data:
#        a.rubric = (data["rubric"] or "").strip()
#    if "rubric_id" in data:
#        a.rubric_id = int(data["rubric_id"]) if data["rubric_id"] is not None else None
#    db.session.commit()
#   return jsonify({"ok": True})
#==================================================

@app.patch("/api/assignments/<int:aid>")
def update_assignment(aid):
    a = Assignment.query.get(aid)
    if not a:
        return jsonify({"error": "assignment not found"}), 404
    data = request.get_json(force=True)
    if "name" in data:
        a.name = (data["name"] or "").strip()
    if "rubric" in data:
        a.rubric = (data["rubric"] or "").strip()
    if "rubric_id" in data:
        a.rubric_id = int(data["rubric_id"]) if data["rubric_id"] is not None else None

    # NEW: due_date handling
    if "due_date" in data:
        raw = data["due_date"]
        if raw is None or raw == "":
            a.due_date = None
        else:
            try:
                a.due_date = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                return jsonify({"error": "due_date must be ISO format (e.g. 2025-11-19T13:00)"}), 400

    db.session.commit()
    return jsonify({"ok": True})


@app.delete("/api/assignments/<int:aid>")
def delete_assignment(aid):
    a = Assignment.query.get(aid)
    if not a:
        return jsonify({"error": "assignment not found"}), 404
    db.session.delete(a)
    db.session.commit()
    return jsonify({"ok": True})

# ----- Submissions: single upload -----
@app.post("/api/upload_submission")
def upload_submission():
    """
    multipart/form-data:
      - student_name
      - assignment_id
      - file (txt/pdf/docx)
    """
    student_name = (request.form.get("student_name") or "").strip()
    assignment_id = request.form.get("assignment_id")
    f = request.files.get("file")

    if not student_name or not assignment_id or not f:
        return jsonify({"error": "student_name, assignment_id and file are required"}), 400
    if not allowed_file(f.filename):
        return jsonify({"error": "Invalid file type. Allowed: txt, pdf, docx"}), 400

    # Save file
    safe_name = secure_filename(f.filename)
    dest = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
    f.save(dest)

    # Create submission
    s = Submission(
        student_name=student_name,
        assignment_id=int(assignment_id),
        file_path=dest,
    )
    db.session.add(s)

    # Grade (safe on errors / quota)
    a = Assignment.query.get(int(assignment_id))
    rubric_text = a.rubric or (Rubric.query.get(a.rubric_id).body if a.rubric_id else "")
    sub_text = extract_text(dest)
    feedback, grade = grade_with_openai(sub_text, rubric_text or "No rubric provided")
    s.ai_feedback = feedback
    s.ai_grade = grade

    db.session.commit()
    return jsonify({"id": s.id, "message": "uploaded and graded"}), 201

# ----- Submissions: multi upload (drag & drop many) -----
@app.post("/api/upload_submissions")
def upload_submissions():
    """
    multipart/form-data:
      - assignment_id
      - files (multiple)

    Expected filename format:
      SubmissionName_YourName.ext
    """
    assignment_id = request.form.get("assignment_id")
    if not assignment_id:
        return jsonify({"error": "assignment_id is required"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "files[] are required"}), 400

    created_ids = []
    a = Assignment.query.get(int(assignment_id))
    rubric_text = a.rubric or (Rubric.query.get(a.rubric_id).body if a.rubric_id else "")

    for f in files:
        if not f or not allowed_file(f.filename):
            continue

        safe_name = secure_filename(f.filename)
        dest = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        f.save(dest)

        # 🔍 Use the new parser on the ORIGINAL filename
        submission_title, student_name = parse_submission_filename(f.filename or safe_name)
        if not student_name:
            # Fallback so we never blow up
            student_name = "Unknown Student"

        s = Submission(
            student_name=student_name,
            assignment_id=int(assignment_id),
            file_path=dest,
        )
        db.session.add(s)
        db.session.flush()
        created_ids.append(s.id)

        # Auto-grade
        sub_text = extract_text(dest)
        feedback, grade = grade_with_openai(sub_text, rubric_text or "No rubric provided")
        s.ai_feedback = feedback
        s.ai_grade = grade

    db.session.commit()
    return jsonify({"created_ids": created_ids}), 201


# ----- Submissions: read / finalize / delete -----
@app.get("/api/submissions/<int:sid>")
def get_submission(sid):
    s = Submission.query.get_or_404(sid)
    return jsonify(s.to_dict_full())

@app.post("/api/submissions/<int:sid>/finalize")
def finalize_submission(sid):
    s = Submission.query.get_or_404(sid)
    data = request.get_json(silent=True) or {}
    final_grade = (data.get("final_grade") or "").strip()
    if not final_grade:
        return jsonify({"error": "final_grade is required"}), 400
    s.final_grade = final_grade
    db.session.commit()
    return jsonify({"ok": True})

@app.delete("/api/submissions/<int:sid>")
def delete_submission(sid):
    s = Submission.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True})

# =========================
# Entrypoint
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
