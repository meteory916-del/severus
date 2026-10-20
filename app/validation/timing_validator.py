from __future__ import annotations

from typing import Any


def _issue(code: str, severity: str, message: str, field: str | None = None) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "field": field or ""}


def validate_timing(variant: dict, input_data: dict) -> list[dict]:
    issues: list[dict] = []
    timeline = variant.get("timeline", [])

    if not isinstance(timeline, list):
        return [_issue("TIMING_ERROR", "critical", "timeline отсутствует или не является списком", "timeline")]

    target = input_data.get("duration_minutes")
    if target is None:
        return [_issue("TIMING_ERROR", "critical", "duration_minutes отсутствует во входных данных", "duration_minutes")]

    durations = [b.get("duration_minutes", 0) for b in timeline if isinstance(b, dict)]
    if sum(durations) != target:
        issues.append(_issue("TIMING_ERROR", "critical", f"Сумма duration_minutes ({sum(durations)}) не равна {target}", "timeline"))

    if timeline and isinstance(timeline[0], dict):
        if timeline[0].get("start_minute") != 0:
            issues.append(_issue("TIMING_ERROR", "critical", "Первый блок начинается не с 0 минуты", "timeline"))

    for block in timeline:
        if isinstance(block, dict) and block.get("duration_minutes", 0) <= 0:
            issues.append(_issue("TIMING_ERROR", "critical", f"duration_minutes <= 0 в блоке '{block.get('block_id', '?')}'", "timeline"))

    for i in range(len(timeline) - 1):
        cur, nxt = timeline[i], timeline[i + 1]
        if not (isinstance(cur, dict) and isinstance(nxt, dict)):
            continue
        expected = cur.get("start_minute", 0) + cur.get("duration_minutes", 0)
        actual = nxt.get("start_minute")
        if actual != expected:
            issues.append(_issue(
                "TIMING_ERROR",
                "critical",
                f"Блок '{nxt.get('block_id', '?')}' начинается в {actual}, ожидалось {expected}",
                "timeline",
            ))

    return issues
