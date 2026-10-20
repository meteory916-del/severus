from __future__ import annotations

import copy
import json
from pathlib import Path

from app.validation import validate_structure

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / "outputs" / name).read_text(encoding="utf-8"))


def _load_input(name: str) -> dict:
    return json.loads((FIXTURES / "inputs" / name).read_text(encoding="utf-8"))


def test_happy_path_no_critical() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_structure(variant, inp)
    assert not [i for i in issues if i["severity"] == "critical"]


def test_broken_references_found() -> None:
    variant = _load("broken_references.json")
    inp = _load_input("05_no_parents.json")
    issues = validate_structure(variant, inp)
    criticals = [i for i in issues if i["severity"] == "critical"]
    assert any("role_id" in i["message"] for i in criticals)
    assert any("material_id" in i["message"] for i in criticals)
    assert any("block_id" in i["message"] for i in criticals)


def test_parents_disabled_with_parent_role_is_critical() -> None:
    variant = _load("parents_violation_variant.json")
    inp = _load_input("05_no_parents.json")
    issues = validate_structure(variant, inp)
    assert any(i["severity"] == "critical" and "parent" in i["message"].lower() for i in issues)


def test_missing_required_field_returns_issue() -> None:
    variant = _load("happy_path_variant.json")
    variant.pop("teacher_instructions")
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_structure(variant, inp)
    assert any(i["code"] == "MISSING_FIELD" and i["field"] == "teacher_instructions" for i in issues)


def test_parents_count_exceeded() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("04_parents_enabled.json")
    inp["participants"]["parents_count"] = 3
    issues = validate_structure(variant, inp)
    assert any("больше parents_count" in i["message"] for i in issues)


def test_too_few_blocks_negative() -> None:
    variant = _load("happy_path_variant.json")
    variant["timeline"] = variant["timeline"][:1]
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_structure(variant, inp)
    assert any(i["code"] == "TOO_FEW_BLOCKS" and i["severity"] == "high" for i in issues)


def test_too_few_blocks_positive() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_structure(variant, inp)
    assert not any(i["code"] == "TOO_FEW_BLOCKS" for i in issues)


def test_printer_required_but_missing() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("08_minimal_resources.json")
    inp["resources"]["printer_required"] = True
    issues = validate_structure(variant, inp)
    assert any("printer" in i["message"].lower() for i in issues)


def test_parents_enabled_without_plan() -> None:
    variant = _load("happy_path_variant.json")
    variant.pop("parent_participation_plan")
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_structure(variant, inp)
    assert any("parent_participation_plan" in i["message"] and i["severity"] == "high" for i in issues)


def test_empty_teacher_script_in_block() -> None:
    variant = _load("happy_path_variant.json")
    variant["timeline"][1]["teacher_script"] = ""
    inp = _load_input("01_happy_path_45min.json")
    issues = validate_structure(variant, inp)
    assert any("teacher_script" in i["message"] and i["severity"] == "high" for i in issues)


def test_school_event_format_no_crash() -> None:
    variant = _load("happy_path_variant.json")
    inp = _load_input("06_school_event.json")
    issues = validate_structure(variant, inp)
    assert isinstance(issues, list)
