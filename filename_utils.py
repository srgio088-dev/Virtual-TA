import os
import re

def parse_submission_filename(original_name: str):
    """
    Expect filenames like:
      'Discussion Post 1 - Social Engineering - Jed Cooper.docx'
      'Lab1 - Jane Doe.pdf'
      'Midterm-1 - John A. Smith.pptx'

    We ALWAYS treat the LAST ' - ' section as the student name.
    Everything before that is the assignment part from the file.
    """
    # strip any path bits
    base = os.path.basename(original_name)

    # remove extension
    base, _ = os.path.splitext(base)

    # turn underscores into spaces, normalize spaces
    base = base.replace("_", " ")
    base = re.sub(r"\s+", " ", base).strip()

    # split on " - " (space-hyphen-space)
    parts = base.split(" - ")

    if len(parts) >= 2:
        student_name = parts[-1].strip()
        assignment_from_file = " - ".join(parts[:-1]).strip()
        return assignment_from_file, student_name

    # fallback if no " - " found
    return base, ""
