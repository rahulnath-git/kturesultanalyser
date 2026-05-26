from __future__ import annotations

import base64
import json
import mimetypes
import os
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from analytics import calculate_batch_analytics
from database import (
    DB_PATH,
    create_batch,
    delete_batch,
    get_batch_records,
    initialise_database,
    list_batches,
    list_grade_config,
    replace_grade_config,
    update_course_credits,
)
from result_parser import parse_result_pdf
from report_exports import (
    generate_excel_report,
    generate_student_register_excel,
    generate_word_report,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def bytes_response(
    handler: BaseHTTPRequestHandler,
    status: int,
    payload: bytes,
    content_type: str,
    file_name: str,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Content-Disposition", f'attachment; filename="{file_name}"')
    handler.end_headers()
    handler.wfile.write(payload)


def no_content_response(handler: BaseHTTPRequestHandler) -> None:
    handler.send_response(HTTPStatus.NO_CONTENT)
    handler.end_headers()


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    if content_length <= 0:
        raise ValueError("The request body is empty.")

    raw_body = handler.rfile.read(content_length)
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("The request body is not valid JSON.") from exc


def batch_payload(batch_id: int) -> dict:
    batch_records = get_batch_records(batch_id)
    if batch_records is None:
        raise KeyError("Batch not found.")

    grade_config = list_grade_config()
    analytics = calculate_batch_analytics(
        batch=batch_records["batch"],
        students=batch_records["students"],
        grades=batch_records["grades"],
        courses=batch_records["courses"],
        grade_config=grade_config,
    )
    return {"gradeConfig": grade_config, "analytics": analytics}


def parse_threshold(query: dict[str, list[str]]) -> float:
    raw_value = query.get("threshold", ["7.0"])[0]
    try:
        threshold = float(raw_value)
    except ValueError as exc:
        raise ValueError("Threshold must be a valid number.") from exc

    if threshold < 0 or threshold > 10:
        raise ValueError("Threshold must be between 0 and 10.")

    return threshold


class ResultAnalyserHandler(BaseHTTPRequestHandler):
    server_version = "KTUResultAnalyser/1.0"

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/health":
                json_response(self, HTTPStatus.OK, {"status": "ok"})
                return

            if path == "/api/dashboard":
                json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "gradeConfig": list_grade_config(),
                        "batches": list_batches(),
                    },
                )
                return

            if path == "/api/batches":
                json_response(self, HTTPStatus.OK, {"batches": list_batches()})
                return

            export_match = self.extract_export_request(path)
            if export_match is not None:
                batch_id, export_type = export_match
                query = parse_qs(parsed.query)
                threshold = parse_threshold(query)
                payload = batch_payload(batch_id)

                if export_type == "excel":
                    file_bytes, file_name = generate_excel_report(
                        payload["analytics"],
                        payload["gradeConfig"],
                        threshold,
                    )
                    bytes_response(
                        self,
                        HTTPStatus.OK,
                        file_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        file_name,
                    )
                    return

                if export_type == "register-excel":
                    file_bytes, file_name = generate_student_register_excel(
                        payload["analytics"],
                        query.get("department", [""])[0],
                        query.get("search", [""])[0],
                    )
                    bytes_response(
                        self,
                        HTTPStatus.OK,
                        file_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        file_name,
                    )
                    return

                if export_type == "word":
                    file_bytes, file_name = generate_word_report(
                        payload["analytics"],
                        payload["gradeConfig"],
                        threshold,
                    )
                    bytes_response(
                        self,
                        HTTPStatus.OK,
                        file_bytes,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        file_name,
                    )
                    return

                raise ValueError("Unsupported export type.")

            if path.startswith("/api/batches/"):
                batch_id = self.extract_batch_id(path)
                json_response(self, HTTPStatus.OK, batch_payload(batch_id))
                return

            self.serve_static(path)
        except KeyError as exc:
            json_response(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            traceback.print_exc()
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Unexpected server error: {exc}"},
            )

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path != "/api/batches":
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "Route not found."})
                return

            payload = read_json_body(self)
            file_name = str(payload.get("fileName", "")).strip()
            file_data = str(payload.get("fileData", "")).strip()
            batch_name = str(payload.get("batchName", "")).strip()

            if not file_name:
                raise ValueError("A PDF file name is required.")
            if not file_data:
                raise ValueError("The uploaded PDF data is missing.")

            try:
                pdf_bytes = base64.b64decode(file_data, validate=True)
            except ValueError as exc:
                raise ValueError("The uploaded PDF data is not valid base64.") from exc

            parsed_batch = parse_result_pdf(pdf_bytes, file_name)
            batch_id = create_batch(parsed_batch, batch_name, file_name, DB_PATH)
            json_response(self, HTTPStatus.CREATED, batch_payload(batch_id))
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            traceback.print_exc()
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Unexpected server error: {exc}"},
            )

    def do_PUT(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            payload = read_json_body(self)

            if path == "/api/grade-config":
                grade_rows = payload.get("grades")
                if not isinstance(grade_rows, list):
                    raise ValueError("The grade configuration must be a list.")

                updated = replace_grade_config(grade_rows, DB_PATH)
                json_response(self, HTTPStatus.OK, {"gradeConfig": updated})
                return

            if path.startswith("/api/batches/") and path.endswith("/courses"):
                batch_id = self.extract_batch_id(path[:-8])
                course_rows = payload.get("courses")
                if not isinstance(course_rows, list):
                    raise ValueError("The course update payload must be a list.")

                update_course_credits(batch_id, course_rows, DB_PATH)
                json_response(self, HTTPStatus.OK, batch_payload(batch_id))
                return

            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Route not found."})
        except KeyError as exc:
            json_response(self, HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            traceback.print_exc()
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Unexpected server error: {exc}"},
            )

    def do_DELETE(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if not path.startswith("/api/batches/"):
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "Route not found."})
                return

            batch_id = self.extract_batch_id(path)
            removed = delete_batch(batch_id, DB_PATH)
            if not removed:
                json_response(self, HTTPStatus.NOT_FOUND, {"error": "Batch not found."})
                return

            no_content_response(self)
        except ValueError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            traceback.print_exc()
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Unexpected server error: {exc}"},
            )

    def serve_static(self, path: str) -> None:
        if path in {"/", ""}:
            self.send_file(INDEX_FILE)
            return

        if not path.startswith("/static/"):
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Route not found."})
            return

        relative_path = path.removeprefix("/static/")
        file_path = (STATIC_DIR / relative_path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())):
            json_response(self, HTTPStatus.FORBIDDEN, {"error": "Access denied."})
            return

        self.send_file(file_path)

    def send_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "File not found."})
            return

        content = file_path.read_bytes()
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def extract_batch_id(path: str) -> int:
        tail = path.rsplit("/", 1)[-1]
        if not tail.isdigit():
            raise ValueError("A valid batch id is required.")
        return int(tail)

    @staticmethod
    def extract_export_request(path: str) -> tuple[int, str] | None:
        parts = path.strip("/").split("/")
        if len(parts) != 5:
            return None
        if parts[0] != "api" or parts[1] != "batches" or parts[3] != "exports":
            return None
        if not parts[2].isdigit():
            raise ValueError("A valid batch id is required.")
        return int(parts[2]), parts[4]

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")


def run() -> None:
    initialise_database(DB_PATH)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ResultAnalyserHandler)
    print(f"KTU Result Analyser is running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
