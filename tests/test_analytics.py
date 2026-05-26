import unittest

from analytics import DEFAULT_GRADE_CONFIG, calculate_batch_analytics


class AnalyticsTests(unittest.TestCase):
    def test_weighted_gpa_and_subject_rollups(self) -> None:
        batch = {"id": 1, "name": "Demo Batch"}
        students = [
            {"id": 1, "register_no": "ATP23CS001", "department_name": "COMPUTER SCIENCE"},
            {"id": 2, "register_no": "ATP23CS002", "department_name": "COMPUTER SCIENCE"},
        ]
        courses = [
            {
                "department_name": "COMPUTER SCIENCE",
                "course_code": "MAT201",
                "course_name": "Discrete Mathematics",
                "credits": 4,
            },
            {
                "department_name": "COMPUTER SCIENCE",
                "course_code": "CST203",
                "course_name": "Data Structures",
                "credits": 2,
            },
        ]
        grades = [
            {"student_id": 1, "course_code": "MAT201", "grade": "S"},
            {"student_id": 1, "course_code": "CST203", "grade": "P"},
            {"student_id": 2, "course_code": "MAT201", "grade": "F"},
            {"student_id": 2, "course_code": "CST203", "grade": "Absent"},
        ]

        analytics = calculate_batch_analytics(
            batch=batch,
            students=students,
            grades=grades,
            courses=courses,
            grade_config=DEFAULT_GRADE_CONFIG,
        )

        student_lookup = {
            student["register_no"]: student for student in analytics["students"]
        }
        self.assertEqual(student_lookup["ATP23CS001"]["gpa"], 8.33)
        self.assertEqual(student_lookup["ATP23CS002"]["gpa"], 0.0)

        subject_lookup = {
            subject["course_code"]: subject for subject in analytics["subjects"]
        }
        self.assertEqual(subject_lookup["MAT201"]["appeared_count"], 2)
        self.assertEqual(subject_lookup["MAT201"]["passed_count"], 1)
        self.assertEqual(subject_lookup["MAT201"]["failed_count"], 1)
        self.assertEqual(subject_lookup["MAT201"]["pass_percentage"], 50.0)
        self.assertEqual(subject_lookup["CST203"]["appeared_count"], 1)
        self.assertEqual(subject_lookup["CST203"]["absent_count"], 1)
        self.assertEqual(subject_lookup["CST203"]["pass_percentage"], 100.0)


if __name__ == "__main__":
    unittest.main()
