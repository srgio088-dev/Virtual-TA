import os
import re

def parse_submission_filename(filename):
    """
    Extract assignment_name and student_name from a filename.
    Splits only on the LAST underscore or dash. Spaces are allowed.
    Example accepted formats:
        AssignmentName_Student_Name.docx
        Assignment Name-Student-Name.pdf
    """
    name, _ = os.path.splitext(filename)

    # Look for last underscore or dash
    match = re.search(r"[_-](?=[^_-]+$)", name)
    if not match:
        return None, None  # No valid delimiter found

    split_index = match.start()

    assignment_raw = name[:split_index]
    student_raw = name[split_index + 1:]

    # Clean up whitespace but DO NOT remove internal spaces
    assignment = assignment_raw.strip()
    student = student_raw.strip()

    return assignment, student
