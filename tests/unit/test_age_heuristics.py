from __future__ import annotations

import json
from pathlib import Path

from app.validation import check_age_heuristics

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / "outputs" / name).read_text(encoding="utf-8"))


def _load_input(name: str) -> dict:
    return json.loads((FIXTURES / "inputs" / name).read_text(encoding="utf-8"))


def test_grade_1_4_long_block_warning() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("02_short_30min_1-4.json")
    issues = check_age_heuristics(variant, inp)
    assert any(i["severity"] == "medium" and "1-4" in i["message"] for i in issues)


def test_grade_9_11_all_short_blocks_warning() -> None:
    variant = _load("happy_path_variant.json")
    for block in variant["timeline"]:
        block["duration_minutes"] = 5
    inp = _load_input("03_long_90min_9-11.json")
    issues = check_age_heuristics(variant, inp)
    assert any(i["severity"] == "low" and "9-11" in i["message"] for i in issues)


def test_grade_1_4_long_word_in_script() -> None:
    variant = _load("happy_path_variant.json")
    variant["timeline"][0]["teacher_script"] = "Используйте преобразовательность мышления."
    inp = _load_input("02_short_30min_1-4.json")
    issues = check_age_heuristics(variant, inp)
    assert any(i["severity"] == "low" and "длиннее 12 букв" in i["message"] for i in issues)


def test_grade_5_8_no_warnings() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("01_happy_path_45min.json")
    issues = check_age_heuristics(variant, inp)
    assert not issues


def test_grade_9_11_with_90min_input() -> None:
    variant = _load("happy_path_variant.json")
    for block in variant["timeline"]:
        block["duration_minutes"] = 5
    inp = _load_input("03_long_90min_9-11.json")
    issues = check_age_heuristics(variant, inp)
    assert any(i["severity"] == "low" for i in issues)
