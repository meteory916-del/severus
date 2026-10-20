from __future__ import annotations

import re
from typing import Any


def _issue(code: str, severity: str, message: str, field: str | None = None) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "field": field or ""}


def check_age_heuristics(variant: dict, input_data: dict) -> list[dict]:
    issues: list[dict] = []
    grade_group = input_data.get("grade_group", "")
    timeline = variant.get("timeline", [])

    if grade_group == "1-4":
        for block in timeline:
            if isinstance(block, dict) and block.get("duration_minutes", 0) > 15:
                issues.append(_issue(
                    "AGE_HEURISTIC",
                    "medium",
                    f"Блок '{block.get('block_id', '?')}' длиннее 15 минут для группы 1-4",
                    "timeline",
                ))
                break

        all_text = " ".join(
            block.get("teacher_script", "") for block in timeline if isinstance(block, dict)
        )
        long_words = re.findall(r"[a-zA-Zа-яА-ЯёЁ]{13,}", all_text)
        if long_words:
            issues.append(_issue(
                "AGE_HEURISTIC",
                "low",
                f"В teacher_script есть слова длиннее 12 букв (например, '{long_words[0]}')",
                "timeline.teacher_script",
            ))

    elif grade_group == "9-11":
        if timeline and all(
            isinstance(b, dict) and b.get("duration_minutes", 0) <= 5 for b in timeline
        ):
            issues.append(_issue(
                "AGE_HEURISTIC",
                "low",
                "Все блоки ≤ 5 минут для группы 9-11 — возможно, слишком коротко",
                "timeline",
            ))

    return issues
