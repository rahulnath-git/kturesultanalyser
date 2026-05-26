from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analytics import DEFAULT_GRADE_CONFIG

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "results.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    exam_name TEXT NOT NULL,
    institution TEXT NOT NULL DEFAULT '',
    source_filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    total_students INTEGER NOT NULL DEFAULT 0,
    total_departments INTEGER NOT NULL DEFAULT 0,
    total_courses INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    register_no TEXT NOT NULL,
    department_name TEXT NOT NULL,
    FOREIGN KEY(batch_id) REFERENCES exam_batches(id) ON DELETE CASCADE,
    UNIQUE(batch_id, register_no)
);

CREATE TABLE IF NOT EXISTS batch_courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    department_name TEXT NOT NULL,
    course_code TEXT NOT NULL,
    course_name TEXT NOT NULL,
    credits REAL NOT NULL DEFAULT 1.0,
    FOREIGN KEY(batch_id) REFERENCES exam_batches(id) ON DELETE CASCADE,
    UNIQUE(batch_id, department_name, course_code)
);

CREATE TABLE IF NOT EXISTS student_grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    course_code TEXT NOT NULL,
    grade TEXT NOT NULL,
    FOREIGN KEY(batch_id) REFERENCES exam_batches(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE(student_id, course_code)
);

CREATE TABLE IF NOT EXISTS grade_config (
    grade TEXT PRIMARY KEY,
    points REAL NOT NULL,
    is_pass INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL
);
"""


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialise_database(db_path: str | Path = DB_PATH) -> None:
    database_path = Path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(database_path) as connection:
        connection.executescript(SCHEMA)
        seed_default_grade_config(connection)


def seed_default_grade_config(connection: sqlite3.Connection) -> None:
    existing_rows = connection.execute(
        "SELECT COUNT(*) AS count FROM grade_config"
    ).fetchone()["count"]
    if existing_rows:
        return

    connection.executemany(
        """
        INSERT INTO grade_config (grade, points, is_pass, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                row["grade"],
                float(row["points"]),
                1 if row["is_pass"] else 0,
                index,
            )
            for index, row in enumerate(DEFAULT_GRADE_CONFIG, start=1)
        ],
    )


def list_grade_config(db_path: str | Path = DB_PATH) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT grade, points, is_pass, sort_order
            FROM grade_config
            ORDER BY sort_order, grade
            """
        ).fetchall()

    return [
        {
            "grade": row["grade"],
            "points": float(row["points"]),
            "is_pass": bool(row["is_pass"]),
        }
        for row in rows
    ]


def replace_grade_config(
    grade_rows: list[dict[str, Any]], db_path: str | Path = DB_PATH
) -> list[dict[str, Any]]:
    normalised_rows: list[tuple[str, float, int, int]] = []
    seen: set[str] = set()

    for index, row in enumerate(grade_rows, start=1):
        grade = " ".join(str(row["grade"]).strip().split())
        if not grade:
            raise ValueError("Grade labels cannot be empty.")

        grade_key = grade.upper()
        if grade_key in seen:
            raise ValueError(f"Duplicate grade found: {grade}")

        seen.add(grade_key)
        normalised_rows.append(
            (grade, float(row["points"]), 1 if row["is_pass"] else 0, index)
        )

    if not normalised_rows:
        raise ValueError("At least one grade configuration row is required.")

    with get_connection(db_path) as connection:
        with connection:
            connection.execute("DELETE FROM grade_config")
            connection.executemany(
                """
                INSERT INTO grade_config (grade, points, is_pass, sort_order)
                VALUES (?, ?, ?, ?)
                """,
                normalised_rows,
            )

    return list_grade_config(db_path)


def create_batch(
    parsed_batch: dict[str, Any],
    batch_name: str,
    source_filename: str,
    db_path: str | Path = DB_PATH,
) -> int:
    departments = parsed_batch["departments"]
    if not departments:
        raise ValueError("The PDF could not be parsed into any department data.")

    uploaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total_students = parsed_batch["student_count"]
    total_departments = len(departments)
    known_courses = {
        (department["name"], course["course_code"])
        for department in departments
        for course in department["courses"]
    }

    display_name = batch_name.strip() or parsed_batch["exam_name"]

    with get_connection(db_path) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO exam_batches (
                    name,
                    exam_name,
                    institution,
                    source_filename,
                    uploaded_at,
                    total_students,
                    total_departments,
                    total_courses
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    display_name,
                    parsed_batch["exam_name"],
                    parsed_batch["institution"],
                    source_filename,
                    uploaded_at,
                    total_students,
                    total_departments,
                    len(known_courses),
                ),
            )
            batch_id = int(cursor.lastrowid)

            for department in departments:
                department_name = department["name"]
                for course in department["courses"]:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO batch_courses (
                            batch_id,
                            department_name,
                            course_code,
                            course_name,
                            credits
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            batch_id,
                            department_name,
                            course["course_code"],
                            course["course_name"],
                            1.0,
                        ),
                    )

                for student in department["students"]:
                    student_cursor = connection.execute(
                        """
                        INSERT INTO students (batch_id, register_no, department_name)
                        VALUES (?, ?, ?)
                        """,
                        (batch_id, student["register_no"], department_name),
                    )
                    student_id = int(student_cursor.lastrowid)

                    for grade_row in student["grades"]:
                        course_key = (department_name, grade_row["course_code"])
                        if course_key not in known_courses:
                            known_courses.add(course_key)
                            connection.execute(
                                """
                                INSERT OR IGNORE INTO batch_courses (
                                    batch_id,
                                    department_name,
                                    course_code,
                                    course_name,
                                    credits
                                )
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    batch_id,
                                    department_name,
                                    grade_row["course_code"],
                                    grade_row["course_code"],
                                    1.0,
                                ),
                            )

                        connection.execute(
                            """
                            INSERT OR REPLACE INTO student_grades (
                                batch_id,
                                student_id,
                                course_code,
                                grade
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                batch_id,
                                student_id,
                                grade_row["course_code"],
                                grade_row["grade"],
                            ),
                        )

            connection.execute(
                "UPDATE exam_batches SET total_courses = ? WHERE id = ?",
                (len(known_courses), batch_id),
            )

    return batch_id


def list_batches(db_path: str | Path = DB_PATH) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                name,
                exam_name,
                institution,
                source_filename,
                uploaded_at,
                total_students,
                total_departments,
                total_courses
            FROM exam_batches
            ORDER BY uploaded_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_batch_records(
    batch_id: int, db_path: str | Path = DB_PATH
) -> dict[str, Any] | None:
    with get_connection(db_path) as connection:
        batch_row = connection.execute(
            """
            SELECT
                id,
                name,
                exam_name,
                institution,
                source_filename,
                uploaded_at,
                total_students,
                total_departments,
                total_courses
            FROM exam_batches
            WHERE id = ?
            """,
            (batch_id,),
        ).fetchone()

        if batch_row is None:
            return None

        course_rows = connection.execute(
            """
            SELECT department_name, course_code, course_name, credits
            FROM batch_courses
            WHERE batch_id = ?
            ORDER BY department_name, course_code
            """,
            (batch_id,),
        ).fetchall()
        student_rows = connection.execute(
            """
            SELECT id, register_no, department_name
            FROM students
            WHERE batch_id = ?
            ORDER BY department_name, register_no
            """,
            (batch_id,),
        ).fetchall()
        grade_rows = connection.execute(
            """
            SELECT student_id, course_code, grade
            FROM student_grades
            WHERE batch_id = ?
            ORDER BY student_id, course_code
            """,
            (batch_id,),
        ).fetchall()

    return {
        "batch": dict(batch_row),
        "courses": [dict(row) for row in course_rows],
        "students": [dict(row) for row in student_rows],
        "grades": [dict(row) for row in grade_rows],
    }


def update_course_credits(
    batch_id: int,
    course_rows: list[dict[str, Any]],
    db_path: str | Path = DB_PATH,
) -> None:
    if not course_rows:
        raise ValueError("No course credit updates were supplied.")

    with get_connection(db_path) as connection:
        with connection:
            for row in course_rows:
                credits = float(row["credits"])
                if credits <= 0:
                    raise ValueError("Credits must be greater than zero.")

                result = connection.execute(
                    """
                    UPDATE batch_courses
                    SET credits = ?
                    WHERE batch_id = ? AND department_name = ? AND course_code = ?
                    """,
                    (
                        credits,
                        batch_id,
                        row["department_name"],
                        row["course_code"],
                    ),
                )
                if result.rowcount == 0:
                    raise ValueError(
                        f"Course not found: {row['department_name']} / {row['course_code']}"
                    )


def delete_batch(batch_id: int, db_path: str | Path = DB_PATH) -> bool:
    with get_connection(db_path) as connection:
        with connection:
            result = connection.execute(
                "DELETE FROM exam_batches WHERE id = ?",
                (batch_id,),
            )
    return result.rowcount > 0
