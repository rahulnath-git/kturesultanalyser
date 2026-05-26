from __future__ import annotations

from collections import defaultdict
from typing import Any

DEFAULT_GRADE_CONFIG = [
    {"grade": "S", "points": 10.0, "is_pass": True},
    {"grade": "A+", "points": 9.0, "is_pass": True},
    {"grade": "A", "points": 8.5, "is_pass": True},
    {"grade": "B+", "points": 8.0, "is_pass": True},
    {"grade": "B", "points": 7.0, "is_pass": True},
    {"grade": "C+", "points": 6.5, "is_pass": True},
    {"grade": "C", "points": 6.0, "is_pass": True},
    {"grade": "D", "points": 5.5, "is_pass": True},
    {"grade": "P", "points": 5.0, "is_pass": True},
    {"grade": "F", "points": 0.0, "is_pass": False},
    {"grade": "FE", "points": 0.0, "is_pass": False},
    {"grade": "Absent", "points": 0.0, "is_pass": False},
]

ABSENT_GRADES = {"ABSENT"}


def normalise_grade(grade: str) -> str:
    return " ".join(str(grade).strip().split())


def build_grade_lookup(grade_config: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in grade_config:
        key = normalise_grade(row["grade"]).upper()
        lookup[key] = {
            "grade": normalise_grade(row["grade"]),
            "points": float(row["points"]),
            "is_pass": bool(row["is_pass"]),
        }
    return lookup


def is_absent_grade(grade: str) -> bool:
    return normalise_grade(grade).upper() in ABSENT_GRADES


def get_grade_points(grade: str, grade_lookup: dict[str, dict[str, Any]]) -> float:
    row = grade_lookup.get(normalise_grade(grade).upper())
    return float(row["points"]) if row else 0.0


def is_passing_grade(grade: str, grade_lookup: dict[str, dict[str, Any]]) -> bool:
    row = grade_lookup.get(normalise_grade(grade).upper())
    return bool(row["is_pass"]) if row else False


def calculate_batch_analytics(
    batch: dict[str, Any],
    students: list[dict[str, Any]],
    grades: list[dict[str, Any]],
    courses: list[dict[str, Any]],
    grade_config: list[dict[str, Any]],
) -> dict[str, Any]:
    grade_lookup = build_grade_lookup(grade_config)
    student_lookup = {student["id"]: student for student in students}
    course_lookup = {
        (course["department_name"], course["course_code"]): course for course in courses
    }
    fallback_course_lookup: dict[str, dict[str, Any]] = {}
    for course in courses:
        fallback_course_lookup.setdefault(course["course_code"], course)

    grades_by_student: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for grade_row in grades:
        grades_by_student[grade_row["student_id"]].append(grade_row)

    subject_rollup: dict[tuple[str, str], dict[str, Any]] = {}
    student_rows: list[dict[str, Any]] = []
    unknown_grades: set[str] = set()

    for student in students:
        student_grade_rows = grades_by_student.get(student["id"], [])
        weighted_points = 0.0
        total_credits = 0.0
        passed_count = 0
        failed_count = 0
        absent_count = 0
        grade_items: list[dict[str, Any]] = []

        for grade_row in student_grade_rows:
            course = course_lookup.get(
                (student["department_name"], grade_row["course_code"])
            ) or fallback_course_lookup.get(grade_row["course_code"])

            credits = float(course["credits"]) if course else 1.0
            course_name = course["course_name"] if course else grade_row["course_code"]
            grade_label = normalise_grade(grade_row["grade"])
            grade_key = grade_label.upper()

            if grade_key not in grade_lookup:
                unknown_grades.add(grade_label)

            points = get_grade_points(grade_label, grade_lookup)
            passed = is_passing_grade(grade_label, grade_lookup)
            absent = is_absent_grade(grade_label)

            weighted_points += points * credits
            total_credits += credits

            if passed:
                passed_count += 1
            elif absent:
                absent_count += 1
            else:
                failed_count += 1

            grade_items.append(
                {
                    "course_code": grade_row["course_code"],
                    "course_name": course_name,
                    "grade": grade_label,
                    "points": round(points, 2),
                    "credits": round(credits, 2),
                }
            )

            subject_key = (student["department_name"], grade_row["course_code"])
            subject_row = subject_rollup.get(subject_key)
            if subject_row is None:
                subject_row = {
                    "department_name": student["department_name"],
                    "course_code": grade_row["course_code"],
                    "course_name": course_name,
                    "credits": credits,
                    "registered_count": 0,
                    "appeared_count": 0,
                    "passed_count": 0,
                    "failed_count": 0,
                    "absent_count": 0,
                }
                subject_rollup[subject_key] = subject_row

            subject_row["registered_count"] += 1
            if absent:
                subject_row["absent_count"] += 1
            else:
                subject_row["appeared_count"] += 1

            if passed:
                subject_row["passed_count"] += 1
            elif not absent:
                subject_row["failed_count"] += 1

        gpa = round(weighted_points / total_credits, 2) if total_credits else 0.0
        student_rows.append(
            {
                "register_no": student["register_no"],
                "department_name": student["department_name"],
                "gpa": gpa,
                "subject_count": len(student_grade_rows),
                "passed_count": passed_count,
                "failed_count": failed_count,
                "absent_count": absent_count,
                "total_credits": round(total_credits, 2),
                "grades": grade_items,
            }
        )

    student_rows.sort(key=lambda row: (-row["gpa"], row["register_no"]))
    top_students = student_rows[:5]
    bottom_students = sorted(student_rows, key=lambda row: (row["gpa"], row["register_no"]))[:5]

    subject_rows = sorted(
        subject_rollup.values(),
        key=lambda row: (row["department_name"], row["course_code"]),
    )
    for subject_row in subject_rows:
        appeared = subject_row["appeared_count"]
        subject_row["credits"] = round(float(subject_row["credits"]), 2)
        subject_row["pass_percentage"] = round(
            (subject_row["passed_count"] / appeared) * 100 if appeared else 0.0,
            2,
        )

    total_students = len(student_rows)
    average_gpa = round(
        sum(student["gpa"] for student in student_rows) / total_students if total_students else 0.0,
        2,
    )

    return {
        "batch": batch,
        "summary": {
            "total_students": total_students,
            "total_departments": len({student["department_name"] for student in students}),
            "total_courses": len(courses),
            "average_gpa": average_gpa,
            "highest_gpa": top_students[0]["gpa"] if top_students else 0.0,
            "lowest_gpa": bottom_students[0]["gpa"] if bottom_students else 0.0,
            "unknown_grades": sorted(unknown_grades),
        },
        "departments": sorted({student["department_name"] for student in students}),
        "top_students": top_students,
        "bottom_students": bottom_students,
        "students": student_rows,
        "subjects": subject_rows,
    }
