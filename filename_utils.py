import os

def parse_submission_filename(original_name: str):
    """
    Expected format (no extension):
        SubmissionName_YourName

    Examples:
        'Discussion Post 1_Jed Cooper.docx'
        'Lab1_JedCooper.pdf'

    We treat EVERYTHING before the last "_" as the submission name,
    and EVERYTHING after it as the student name.
    """
    # Just the file name, no directories
    base = os.path.basename(original_name)

    # Drop extension
    base, _ = os.path.splitext(base)

    # If there is at least one underscore, split on the LAST one
    if "_" in base:
        submission_part, student_part = base.rsplit("_", 1)

        # Clean up spaces/underscores in student name
        student_clean = student_part.replace("_", " ").strip()
        submission_clean = submission_part.strip()

        return submission_clean, student_clean

    # Fallback: no underscore; we can't separate, so treat entire
    # stem as submission name and leave student blank
    return base, ""
