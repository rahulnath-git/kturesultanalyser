from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

DEPARTMENT_PATTERN = re.compile(
    r"^(?P<name>.+?)\[[^\]]+\]\s+\(Generated on .+\)$"
)
COURSE_PATTERN = re.compile(r"^(?P<code>[A-Z]{2,4}\d{3}[A-Z]?)\s+(?P<name>.+)$")
REGISTER_PATTERN = re.compile(
    r"^(?P<register_no>[A-Z]{2,8}\d{2}[A-Z]{2,4}\d{3})\s+(?P<grades>.+)$"
)
GRADE_PATTERN = re.compile(r"(?P<course_code>[A-Z]{2,4}\d{3}[A-Z]?)\((?P<grade>[^)]+)\)")


def normalise_line(line: str) -> str:
    return " ".join(line.replace("\xa0", " ").split())


def build_logical_lines(raw_lines: list[str]) -> list[str]:
    normalised_lines = [normalise_line(raw_line) for raw_line in raw_lines]
    logical_lines: list[str] = []
    index = 0

    while index < len(normalised_lines):
        line = normalised_lines[index]
        if not line:
            index += 1
            continue

        if "[" in line and "(Generated on" in line and not line.endswith(")"):
            parts = [line]
            index += 1

            while index < len(normalised_lines):
                next_line = normalised_lines[index]
                index += 1

                if not next_line:
                    continue

                parts.append(next_line)
                if next_line.endswith(")"):
                    break

            logical_lines.append(" ".join(parts))
            continue

        logical_lines.append(line)
        index += 1

    return logical_lines


def parse_result_pdf(file_bytes: bytes, source_filename: str = "") -> dict[str, Any]:
    reader = PdfReader(io.BytesIO(file_bytes))
    raw_lines: list[str] = []
    for page in reader.pages:
        raw_lines.extend((page.extract_text() or "").splitlines())

    logical_lines = build_logical_lines(raw_lines)

    exam_name = ""
    institution = ""
    departments: list[dict[str, Any]] = []
    current_department: dict[str, Any] | None = None
    current_course: dict[str, Any] | None = None
    current_student: dict[str, Any] | None = None
    state = "intro"

    for line in logical_lines:
        if line.startswith("Exam Centre:"):
            institution = line.split(":", 1)[1].strip()
            continue

        if not exam_name and "Exam" in line and "Result" in line:
            exam_name = line
            continue

        if line in {
            "APJ ABDUL KALAM TECHNOLOGICAL UNIVERSITY",
            "Thiruvananthapuram, Kerala, INDIA",
            "*TBP -To Be Published Soon",
        }:
            continue

        department_match = DEPARTMENT_PATTERN.match(line)
        if department_match:
            current_department = {
                "name": department_match.group("name").strip(),
                "courses": [],
                "students": [],
            }
            departments.append(current_department)
            current_course = None
            current_student = None
            state = "department"
            continue

        if line == "Course Code Course":
            current_course = None
            current_student = None
            state = "courses"
            continue

        if line == "Register No Course Code (Grade)":
            current_course = None
            current_student = None
            state = "students"
            continue

        if current_department is None:
            continue

        if state == "courses":
            course_match = COURSE_PATTERN.match(line)
            if course_match:
                current_course = {
                    "course_code": course_match.group("code"),
                    "course_name": course_match.group("name").strip(),
                }
                current_department["courses"].append(current_course)
            elif current_course is not None:
                current_course["course_name"] = (
                    f"{current_course['course_name']} {line}".strip()
                )
            continue

        if state == "students":
            register_match = REGISTER_PATTERN.match(line)
            if register_match:
                current_student = {
                    "register_no": register_match.group("register_no"),
                    "grades_text": register_match.group("grades").strip(),
                }
                current_department["students"].append(current_student)
            elif current_student is not None:
                current_student["grades_text"] = (
                    f"{current_student['grades_text']} {line}".strip()
                )

    total_students = 0
    total_courses = 0
    for department in departments:
        total_courses += len(department["courses"])
        for student in department["students"]:
            student["grades"] = [
                {
                    "course_code": match.group("course_code"),
                    "grade": normalise_line(match.group("grade")),
                }
                for match in GRADE_PATTERN.finditer(student["grades_text"])
            ]
            del student["grades_text"]
            total_students += 1

    return {
        "exam_name": exam_name or Path(source_filename).stem,
        "institution": institution,
        "departments": departments,
        "student_count": total_students,
        "course_count": total_courses,
    }


def parse_result_pdf_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    return parse_result_pdf(file_path.read_bytes(), file_path.name)
