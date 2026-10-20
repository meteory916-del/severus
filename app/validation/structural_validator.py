from __future__ import annotations

from typing import Any


def _issue(
    code: str,
    severity: str,
    message: str,
    field: str | None = None,
) -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "field": field or ""}


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def validate_structure(variant: dict, input_data: dict) -> list[dict]:
    issues: list[dict] = []

    concept = variant.get("concept", {})
    timeline = variant.get("timeline", [])
    roles = variant.get("roles", [])
    materials = variant.get("materials", [])
    teacher_instructions = variant.get("teacher_instructions")

    # --- Обязательные поля и типы ---
    if not _is_non_empty_string(concept.get("summary")):
        issues.append(_issue("MISSING_FIELD", "high", "concept.summary отсутствует или пуст", "concept.summary"))
    if not _is_non_empty_string(concept.get("goal")):
        issues.append(_issue("MISSING_FIELD", "high", "concept.goal отсутствует или пуст", "concept.goal"))
    if not isinstance(timeline, list):
        issues.append(_issue("MISSING_FIELD", "critical", "timeline отсутствует или не является списком", "timeline"))
        timeline = []
    if not isinstance(roles, list):
        issues.append(_issue("MISSING_FIELD", "critical", "roles отсутствует или не является списком", "roles"))
        roles = []
    if not isinstance(materials, list):
        issues.append(_issue("MISSING_FIELD", "critical", "materials отсутствует или не является списком", "materials"))
        materials = []

    # teacher_instructions может быть строкой или списком
    if not (_is_non_empty_string(teacher_instructions) or _is_non_empty_list(teacher_instructions)):
        issues.append(_issue("MISSING_FIELD", "high", "teacher_instructions отсутствует или пуст", "teacher_instructions"))

    # --- Минимум 2 блока ---
    if isinstance(timeline, list) and len(timeline) < 2:
        issues.append(_issue("TOO_FEW_BLOCKS", "high", f"В timeline только {len(timeline)} блок(ов), минимум 2", "timeline"))

    # --- Ссылочная целостность ---
    role_ids = {r.get("role_id") for r in roles if isinstance(r, dict)}
    material_ids = {m.get("material_id") for m in materials if isinstance(m, dict)}
    block_ids = {b.get("block_id") for b in timeline if isinstance(b, dict)}

    for block in timeline:
        if not isinstance(block, dict):
            continue
        for rid in block.get("role_ids", []):
            if rid not in role_ids:
                issues.append(_issue("MISSING_FIELD", "critical", f"role_id '{rid}' не найден в roles", "timeline.role_ids"))
        for mid in block.get("material_ids", []):
            if mid not in material_ids:
                issues.append(_issue("MISSING_FIELD", "critical", f"material_id '{mid}' не найден в materials", "timeline.material_ids"))
        if not _is_non_empty_string(block.get("teacher_script")):
            issues.append(_issue("MISSING_FIELD", "high", f"teacher_script в блоке '{block.get('block_id', '?')}' пуст", "timeline.teacher_script"))

    # --- Логика родителей ---
    parent_plan = variant.get("parent_participation_plan", {})
    parent_plan_enabled = parent_plan.get("enabled", False) if isinstance(parent_plan, dict) else False

    if isinstance(parent_plan, dict):
        for bid in parent_plan.get("block_ids", []):
            if bid not in block_ids:
                issues.append(_issue("MISSING_FIELD", "critical", f"block_id '{bid}' из parent_participation_plan не найден в timeline", "parent_participation_plan.block_ids"))

    parents_enabled = input_data.get("participants", {}).get("parents_enabled", False)
    parents_count = input_data.get("participants", {}).get("parents_count", 0)

    if not parents_enabled:
        for role in roles:
            if isinstance(role, dict) and role.get("participant_type") == "parent":
                issues.append(_issue("MISSING_FIELD", "critical", "participant_type='parent' при parents_enabled=false", "roles"))
        if parent_plan_enabled:
            issues.append(_issue("MISSING_FIELD", "critical", "parent_participation_plan.enabled=true при parents_enabled=false", "parent_participation_plan"))
    else:
        if not parent_plan_enabled:
            issues.append(_issue("MISSING_FIELD", "high", "parent_participation_plan отсутствует или enabled=false при parents_enabled=true", "parent_participation_plan"))
        for block in timeline:
            if not isinstance(block, dict):
                continue
            total_parents = 0
            for rid in block.get("role_ids", []):
                for role in roles:
                    if isinstance(role, dict) and role.get("role_id") == rid and role.get("participant_type") == "parent":
                        total_parents += role.get("count", 0)
            if total_parents > parents_count:
                issues.append(_issue(
                    "MISSING_FIELD",
                    "critical",
                    f"В блоке '{block.get('block_id', '?')}' родителей ({total_parents}) больше parents_count ({parents_count})",
                    "roles",
                ))

    # --- Ресурсы: printer_required ---
    resources = input_data.get("resources", {})
    if isinstance(resources, dict) and resources.get("printer_required", False):
        has_printer = any(
            isinstance(m, dict) and "printer" in str(m.get("material_id", "")).lower()
            for m in materials
        )
        if not has_printer:
            issues.append(_issue("MISSING_FIELD", "high", "printer_required=true, но printer отсутствует в materials", "materials"))

    return issues
