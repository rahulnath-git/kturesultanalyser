# KTU Result Analyser

KTU Result Analyser is a lightweight web application for parsing KTU result PDFs, storing result batches in SQLite, and generating GPA and subject analytics through a plain HTML, CSS, and JavaScript interface.

## What the application does

- Uploads a KTU-format result PDF and stores it as a named batch.
- Extracts department, course, register number, subject code, and grade details from the PDF.
- Lets you edit the grade-to-point map used for GPA calculation.
- Lets you update course credits per subject so GPA can be weighted correctly.
- Shows per-student GPA, subject-wise pass statistics, class average GPA, top 5 students, and bottom 5 students.
- Keeps uploaded batches in a local SQLite database for later review.

## Technology stack

- Frontend: HTML, CSS, vanilla JavaScript
- Backend: Python 3
- Database: SQLite
- PDF parsing: `pypdf`

## Project structure

```text
app/
├── app.py                  # HTTP server and API routes
├── analytics.py            # GPA and reporting logic
├── database.py             # SQLite schema and persistence helpers
├── result_parser.py        # KTU PDF parser
├── requirements.txt
├── static/
│   ├── app.js
│   ├── index.html
│   ├── styles.css
│   └── assets/
├── sample_data/
│   └── ktu-sample-results.pdf
├── tests/
│   ├── test_analytics.py
│   └── test_parser.py
└── docs/
    └── architecture.md
```

## Local deployment

### 1. Create and activate a virtual environment

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run the server

```powershell
python app.py
```

The application will start at:

```text
http://127.0.0.1:8000
```

### 4. Open the application

Visit `http://127.0.0.1:8000` in your browser, upload a KTU result PDF, and start analysing.

## Running tests

```powershell
python -m unittest discover -s tests
```

## Notes and assumptions

- The parser is designed for text-based KTU result PDFs similar to the supplied sample.
- Image-only scanned PDFs are not supported.
- Course credits are editable because the PDF does not include credit values.
- GPA is calculated using the configured grade points and the stored course credits.
- Grades not present in the configured grade map are treated as zero points and flagged in the dashboard.

## Default grade scale

The seeded grade scale is:

| Grade | Points | Pass |
| --- | ---: | :---: |
| S | 10.0 | Yes |
| A+ | 9.0 | Yes |
| A | 8.5 | Yes |
| B+ | 8.0 | Yes |
| B | 7.0 | Yes |
| C+ | 6.5 | Yes |
| C | 6.0 | Yes |
| D | 5.5 | Yes |
| P | 5.0 | Yes |
| F | 0.0 | No |
| FE | 0.0 | No |
| Absent | 0.0 | No |

## API overview

- `GET /api/dashboard`: returns grade config and stored batches
- `POST /api/batches`: stores a new parsed PDF batch
- `GET /api/batches/{id}`: returns analytics for a selected batch
- `PUT /api/grade-config`: updates the grade-to-point mapping
- `PUT /api/batches/{id}/courses`: updates course credits
- `DELETE /api/batches/{id}`: removes a stored batch

## Sample data

The supplied sample PDF is copied into `sample_data/ktu-sample-results.pdf` so you can test the parser quickly after setup.
