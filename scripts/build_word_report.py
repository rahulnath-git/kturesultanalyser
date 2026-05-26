from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import report_exports


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage: python build_word_report.py <context.json> <output.docx> [header-image]"
        )

    context_path = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()
    header_image_path = (
        Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else report_exports.HEADER_IMAGE_PATH
    )

    if not context_path.exists():
        raise FileNotFoundError(f"Context file not found: {context_path}")

    report_exports.HEADER_IMAGE_PATH = header_image_path

    context = json.loads(context_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(report_exports.generate_word_report_python(context))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
