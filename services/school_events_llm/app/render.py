"""Сборка ответа фронтенду по замороженному контракту 02 (ТЗ 14.6).

Внутренние поля контракта 03 (values_to_mechanics, pupil_grouping, fact_claims,
family_task) в ответ не попадают: они выводятся в существующие поля по шаблону.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .catalog import Catalog
from .generation.grouping import describe
from .normalize import NormalizedRequest
from .validation.checks import Issue, report_status

SCHEMA_VERSION_02 = "1.2"

MECHANIC_LABELS = {
    "family_research": "семейное исследование",
    "team_task": "командная задача",
    "source_work": "работа с источниками",
    "joint_product": "совместный продукт",
    "culture_comparison": "сравнительное изучение культур",
    "real_problem_solving": "решение реальной задачи",
    "class_collective_task": "общая задача всего класса",
    "pair_task": "работа в парах",
    "discussion": "обсуждение",
}

ROLE_KEYS = ("role_id", "participant_type", "role_mode", "title", "count", "block_ids")
BLOCK_KEYS = ("block_id", "start_minute", "duration_minutes", "title", "purpose", "teacher_script", "pupil_actions", "role_ids", "material_ids")
MATERIAL_KEYS = ("material_id", "type", "title", "used_in_blocks", "audience", "content", "teacher_notes", "print_required", "dependencies", "estimated_preparation_minutes")


def now_iso() -> str:
    """Возвращает текущую дату и время в формате ISO для метаданных результата.

    Возвращает:
        str.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def value_lines(v: dict[str, Any], n: NormalizedRequest, catalog: Catalog) -> list[str]:
    """Преобразует внутренние ценности и механики в строки для внешнего контракта.

    Параметры:
        `v`, `n`, `catalog`.

    Возвращает:
        list[str].
    """
    titles = {b["block_id"]: b["title"] for b in v["timeline"]}
    lines = [f"Воспитательная задача: {g[0].lower() + g[1:] if g else g}" for g in n.educational_goals]
    for rec in v["concept"].get("values_to_mechanics", []):
        value = catalog.values.get(rec["value_id"], {"title": rec["value_id"]})
        blocks = ", ".join(f"«{titles[b]}»" for b in rec.get("block_ids", []) if b in titles)
        label = MECHANIC_LABELS.get(rec["mechanic_type"], rec["mechanic_type"])
        mechanic = rec["mechanic"].rstrip(".")
        mechanic = mechanic[:1].lower() + mechanic[1:]
        lines.append(f"Ценность «{value['title']}» → {label}: {mechanic} (блоки: {blocks})")
    return lines


def render_variant(v: dict[str, Any], n: NormalizedRequest, catalog: Catalog, issues: list[Issue], *,
                   revision: int = 1, checked_at: str | None = None) -> dict[str, Any]:
    """Преобразует внутренний вариант контракта 03 во внешний вариант замороженного контракта 02.

    Параметры:
        `v`, `n`, `catalog`, `issues`, `revision`, `checked_at`.

    Возвращает:
        dict[str, Any].
    """
    grouping = v.get("pupil_grouping") or {}
    sizes = grouping.get("group_sizes") or [n.pupils_count]

    roles = []
    for r in v["roles"]:
        item = {k: r[k] for k in ROLE_KEYS if k in r and r[k] is not None}
        if r["participant_type"] != "parent":
            item.pop("role_mode", None)
        if r["participant_type"] == "pupils_group" and r["count"] == n.pupils_count and len(sizes) > 1 and "(" not in r["title"]:
            item["title"] = f"{r['title']} ({describe(sizes)})"
        roles.append(item)

    instructions = list(v["teacher_instructions"])
    if len(sizes) > 1:
        numbers = ", ".join(str(x) for x in sizes)
        if not any(numbers in line for line in instructions):
            instructions.insert(0, f"Заранее продумать деление класса: {describe(sizes)}.")
    for m in v["materials"]:
        if m.get("family_task"):
            instructions.append(f"Задание семьям «{m['title']}» выдать за несколько дней до мероприятия и напомнить, что оно необязательное; на мероприятии делятся только желающие.")

    claim_sources = {c["source_id"] for c in v.get("fact_claims", []) if c.get("source_id") and not c.get("needs_teacher_check")}
    sources = []
    for sid in sorted(claim_sources):
        src = catalog.sources.get(sid)
        if src:
            sources.append({"source_id": sid, "title": src.get("title", ""), "publisher": src.get("publisher", ""), "url": src.get("url", "")})

    variant = {
        "variant_id": v["variant_id"],
        "revision": revision,
        "status": "completed" if report_status(issues) != "blocked" else "failed",
        "title": v["title"],
        "concept": {
            "summary": v["concept"]["summary"],
            "goal": v["concept"]["goal"],
            "tasks": value_lines(v, n, catalog) + list(v["concept"]["tasks"]),
            "expected_outcomes": list(v["concept"]["expected_outcomes"]),
        },
        "roles": roles,
        "timeline": [{k: b[k] for k in BLOCK_KEYS} for b in v["timeline"]],
        "materials": [{k: m[k] for k in MATERIAL_KEYS} for m in v["materials"]],
    }
    if n.parents_enabled and v.get("parent_participation_plan"):
        variant["parent_participation_plan"] = v["parent_participation_plan"]
    variant["teacher_instructions"] = instructions
    variant["sources"] = sources
    variant["quality_report"] = {
        "status": report_status(issues),
        "issues": [{"code": i.code, "severity": i.severity, "location": i.location, "message": i.message} for i in issues],
        "checked_at": checked_at or now_iso(),
    }
    return variant


def render_project(*, job_id: str, project_id: str, n: NormalizedRequest, variants: list[dict[str, Any]],
                   requested: int, model_key: str, prompt_version: str, catalog_version: str, finished: bool = True) -> dict[str, Any]:
    """Собирает итоговый проект контракта 02 из нормализованного запроса и готовых вариантов.

    Параметры:
        `job_id`, `project_id`, `n`, `variants`, `requested`, `model_key`, `prompt_version`, `catalog_version`, `finished`.

    Возвращает:
        dict[str, Any].
    """
    done = [x for x in variants if x["status"] == "completed"]
    if not finished:
        status = "running"
    elif len(done) == requested:
        status = "completed"
    elif done:
        status = "partial"
    else:
        status = "failed"
    return {
        "schema_version": SCHEMA_VERSION_02,
        "job_id": job_id,
        "project_id": project_id,
        "status": status,
        "requested_variants": requested,
        "completed_variants": len(done),
        "input": n.effective_input,
        "variants": done,
        "generation_meta": {"model_key": model_key, "prompt_version": prompt_version, "catalog_version": catalog_version},
    }