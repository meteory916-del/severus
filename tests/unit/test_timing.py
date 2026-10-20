from __future__ import annotations

import json
from pathlib import Path

from app.validation import validate_timing

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / "outputs" / name).read_text(encoding="utf-8"))


def _load_input(name: str) -> dict:
    return json.loads((FIXTURES / "inputs" / name).read_text(encoding="utf-8"))


def test_happy_path_no_critical() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_timing(variant, inp)
    assert not [i for i in issues if i["severity"] == "critical"]


def test_broken_timing_found() -> None:
    variant = _load("broken_timing.json")
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_timing(variant, inp)
    assert any(i["severity"] == "critical" for i in issues)
