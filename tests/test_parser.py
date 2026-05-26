from pathlib import Path
import unittest

from result_parser import parse_result_pdf_file


BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PDF = BASE_DIR / "sample_data" / "ktu-sample-results.pdf"


class ParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parsed = parse_result_pdf_file(SAMPLE_PDF)

    def test_exam_name_is_detected(self) -> None:
        self.assertIn("B.Tech S5", self.parsed["exam_name"])

    def test_departments_are_extracted(self) -> None:
        department_names = {department["name"] for department in self.parsed["departments"]}
        self.assertIn("MECHANICAL ENGINEERING", department_names)
        self.assertIn("CIVIL ENGINEERING", department_names)
        self.assertIn("ELECTRONICS & COMMUNICATION ENGG", department_names)

    def test_wrapped_course_name_is_rebuilt(self) -> None:
        electronics_department = next(
            department
            for department in self.parsed["departments"]
            if department["name"] == "ELECTRONICS & COMMUNICATION ENGG"
        )
        course_lookup = {
            course["course_code"]: course["course_name"]
            for course in electronics_department["courses"]
        }
        self.assertIn("SIMULATION LAB", course_lookup["ECL331"])

    def test_wrapped_student_grade_line_is_rebuilt(self) -> None:
        mechanical_department = next(
            department
            for department in self.parsed["departments"]
            if department["name"] == "MECHANICAL ENGINEERING"
        )
        target_student = next(
            student
            for student in mechanical_department["students"]
            if student["register_no"] == "ATP23ME002"
        )
        grade_lookup = {
            row["course_code"]: row["grade"]
            for row in target_student["grades"]
        }
        self.assertEqual(grade_lookup["MEL331"], "S")


if __name__ == "__main__":
    unittest.main()
