from __future__ import annotations

import json
from pathlib import Path

from app.core.config import REPO_ROOT
from app.main import create_app

CONTRACT = Path(REPO_ROOT) / "contracts" / "openapi.json"


def test_committed_openapi_contract_is_current() -> None:
    expected = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert create_app().openapi() == expected, "Run scripts/export_openapi.py and commit contracts/openapi.json"


def test_api_routes_are_versioned() -> None:
    paths = create_app().openapi()["paths"]
    for path in paths:
        assert path == "/health" or path.startswith("/api/v1/"), path
