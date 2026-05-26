import unittest
from io import BytesIO

from docx import Document
from openpyxl import load_workbook

from analytics import DEFAULT_GRADE_CONFIG
from report_exports import (
    build_report_context,
    generate_excel_report,
    generate_student_register_excel,
    generate_word_report,
)


class ReportExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analytics = {
            "batch": {
                "id": 1,
                "name": "Demo Batch",
                "exam_name": "Demo Exam",
                "institution": "ASET",
            },
            "summary": {
                "total_students": 4,
                "total_departments": 2,
                "total_courses": 3,
                "average_gpa": 6.95,
                "highest_gpa": 9.1,
                "lowest_gpa": 3.5,
                "unknown_grades": [],
            },
            "top_students": [
                {"register_no": "ATP23CS001", "department_name": "CSE", "gpa": 9.1},
                {"register_no": "ATP23EC001", "department_name": "ECE", "gpa": 8.4},
            ],
            "bottom_students": [
                {"register_no": "ATP23EC002", "department_name": "ECE", "gpa": 3.5},
            ],
            "subjects": [
                {
                    "department_name": "CSE",
                    "course_code": "CST301",
                    "course_name": "Compiler Design",
                    "credits": 4,
                    "appeared_count": 2,
                    "passed_count": 1,
                    "failed_count": 1,
                    "absent_count": 0,
                    "pass_percentage": 50.0,
                }
            ],
            "students": [
                {
                    "register_no": "ATP23CS001",
                    "department_name": "CSE",
                    "gpa": 9.1,
                    "subject_count": 2,
                    "passed_count": 2,
                    "failed_count": 0,
                    "absent_count": 0,
                    "grades": [
                        {"course_code": "CST301", "grade": "A+", "points": 9.0},
                        {"course_code": "MCN301", "grade": "S", "points": 10.0},
                    ],
                },
                {
                    "register_no": "ATP23CS002",
                    "department_name": "CSE",
                    "gpa": 5.8,
                    "subject_count": 2,
                    "passed_count": 1,
                    "failed_count": 1,
                    "absent_count": 0,
                    "grades": [
                        {"course_code": "CST301", "grade": "F", "points": 0.0},
                        {"course_code": "MCN301", "grade": "P", "points": 5.0},
                    ],
                },
                {
                    "register_no": "ATP23EC001",
                    "department_name": "ECE",
                    "gpa": 8.4,
                    "subject_count": 2,
                    "passed_count": 2,
                    "failed_count": 0,
                    "absent_count": 0,
                    "grades": [
                        {"course_code": "ECT301", "grade": "A", "points": 8.5},
                        {"course_code": "MCN301", "grade": "A+", "points": 9.0},
                    ],
                },
                {
                    "register_no": "ATP23EC002",
                    "department_name": "ECE",
                    "gpa": 3.5,
                    "subject_count": 2,
                    "passed_count": 0,
                    "failed_count": 1,
                    "absent_count": 1,
                    "grades": [
                        {"course_code": "ECT301", "grade": "F", "points": 0.0},
                        {"course_code": "MCN301", "grade": "Absent", "points": 0.0},
                    ],
                },
            ],
        }

    def test_report_context_builds_failed_and_threshold_rows(self) -> None:
        context = build_report_context(self.analytics, DEFAULT_GRADE_CONFIG, threshold=7.0)
        self.assertEqual(len(context["failed_students"]), 2)
        self.assertEqual(context["failed_students"][0]["failed_subjects"][0], "CST301 (F)")
        self.assertEqual(len(context["threshold_students"]), 2)
        self.assertEqual(context["threshold_counts"][0]["department_name"], "CSE")

    def test_excel_export_generates_bytes(self) -> None:
        file_bytes, file_name = generate_excel_report(
            self.analytics,
            DEFAULT_GRADE_CONFIG,
            threshold=7.0,
        )
        self.assertTrue(file_name.endswith(".xlsx"))
        self.assertGreater(len(file_bytes), 0)
        self.assertEqual(file_bytes[:2], b"PK")

    def test_word_export_generates_bytes(self) -> None:
        file_bytes, file_name = generate_word_report(
            self.analytics,
            DEFAULT_GRADE_CONFIG,
            threshold=7.0,
        )
        self.assertTrue(file_name.endswith(".docx"))
        self.assertGreater(len(file_bytes), 0)
        self.assertEqual(file_bytes[:2], b"PK")
        self.assertIsInstance(BytesIO(file_bytes), BytesIO)
        document = Document(BytesIO(file_bytes))
        document_text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )
        table_text = "\n".join(
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        )
        self.assertIn("ATP23CS001", f"{document_text}\n{table_text}")

    def test_register_excel_export_respects_filters(self) -> None:
        file_bytes, file_name = generate_student_register_excel(
            self.analytics,
            department="CSE",
            search="002",
        )
        self.assertTrue(file_name.endswith(".xlsx"))
        self.assertEqual(file_bytes[:2], b"PK")
        workbook = load_workbook(BytesIO(file_bytes), data_only=True)
        sheet = workbook["GPA Register"]
        self.assertEqual(sheet["A9"].value, "ATP23CS002")
        self.assertIsNone(sheet["A10"].value)
