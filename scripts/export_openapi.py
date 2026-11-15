"""Write the backend OpenAPI contract to contracts/openapi.json.

Usage (from the repository root):

    .venv\\Scripts\\python.exe scripts\\export_openapi.py          # write
    .venv\\Scripts\\python.exe scripts\\export_openapi.py --check  # fail if out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.main import create_app  # noqa: E402

OUTPUT = REPO_ROOT / "contracts" / "openapi.json"


def render() -> str:
    # Generating the schema does not start the app, touch the database or read private data.
    return json.dumps(create_app().openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print("contracts/openapi.json is out of date. Run scripts/export_openapi.py.")
            return 1
        print("contracts/openapi.json is up to date.")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
