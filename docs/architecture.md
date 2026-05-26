# Architecture Notes

## Overview

The application is intentionally simple:

- A single Python HTTP server exposes JSON endpoints and serves static frontend assets.
- Result data is persisted in SQLite.
- GPA and reporting are calculated dynamically when a batch is viewed so grade scale changes take effect immediately.

## Backend modules

### `app.py`

- Starts the HTTP server.
- Serves `index.html`, CSS, JavaScript, and asset files.
- Exposes the API endpoints for uploads, configuration, batch retrieval, and deletion.

### `result_parser.py`

- Reads the PDF with `pypdf`.
- Detects department blocks, course lists, and student result rows.
- Rebuilds wrapped course names and wrapped student grade lines across page breaks.
- Extracts `COURSE_CODE(GRADE)` tokens into structured records.

### `database.py`

- Creates the SQLite schema automatically.
- Seeds the default grade scale on first run.
- Stores batches, students, subject rows, and grade entries.
- Supports course credit updates and batch deletion.

### `analytics.py`

- Converts the saved grade configuration into a fast lookup table.
- Computes weighted GPA for each student using subject credits.
- Aggregates subject pass, fail, absent, and pass percentage metrics.
- Produces dashboard-ready rankings and summary data.

## Database schema

### `exam_batches`

Stores one row per uploaded PDF batch.

### `students`

Stores each register number inside a batch, with department name.

### `batch_courses`

Stores department-wise course rows and credits.

### `student_grades`

Stores one subject-grade row per student.

### `grade_config`

Stores the editable grade-to-point mapping and pass flag.

## Parser strategy

The parser uses a state-based scan of extracted text:

1. Detect department heading.
2. Read the course list until `Register No Course Code (Grade)`.
3. Read student rows.
4. Merge continuation lines into the previous course or student row.
5. Extract grades using a `COURSE_CODE(GRADE)` regular expression.

This approach works well for the supplied KTU sample because the PDF is text-based and keeps the printed structure in the extracted text.

## GPA calculation

For each student:

1. Find all stored subject grades.
2. Match each grade with its configured point value.
3. Multiply points by the stored course credit.
4. Divide the total weighted points by the total credits.

Grades marked absent are excluded from the `appeared` count but still contribute zero points if they exist in the subject list for the student.

## Extension points

- Add authentication if the tool moves beyond local or intranet use.
- Replace the standard-library HTTP server with Flask or FastAPI if the app needs richer middleware support.
- Add CSV or Excel export for report downloads.
- Add OCR support if scanned PDFs need to be processed later.
