"""Читаемая версия варианта (Markdown) - для педагогов и экспертной оценки."""

from __future__ import annotations

from typing import Any

FORMAT = {"class_hour": "классный час", "school_event": "общешкольное мероприятие", "interactive_lesson": "интерактивное занятие"}
QUALITY_STATUS = {"passed": "замечаний нет", "warning": "есть замечания", "failed": "есть критические ошибки"}
SEVERITY = {"critical": "Критично", "warning": "Замечание", "info": "Справка"}


def issue_place(v: dict[str, Any], location: str) -> str:
    """Переводит место проблемы (`timeline.block_02`, `materials.card_task`, `roles.parent_helpers`) в понятное название.

    Параметры:
        v: вариант; location: поле `location` проблемы.

    Возвращает:
        Например «блок «Встреча и цель» (0-5 мин)»; пустую строку, если место не относится к блоку, материалу или роли.
    """
    kind, _, key = location.partition(".")
    key = key.split(".")[0]
    if kind == "timeline":
        for b in v.get("timeline", []):
            if b["block_id"] == key:
                end = b["start_minute"] + b["duration_minutes"]
                return f"блок «{b['title']}» ({b['start_minute']}-{end} мин)"
    if kind == "materials":
        for m in v.get("materials", []):
            if m["material_id"] == key:
                return f"материал «{m['title']}»"
    if kind == "roles":
        for r in v.get("roles", []):
            if r["role_id"] == key:
                return f"роль «{r['title']}»"
    return ""


def variant_to_markdown(v: dict[str, Any], inp: dict[str, Any] | None = None, event_title: str | None = None) -> str:
    """Формирует читаемую Markdown-проекцию готового варианта для локальной диагностики.

    Параметры:
        `v`, `inp`, `event_title`.

    Возвращает:
        str.
    """
    out: list[str] = [f"# {v['title']}", ""]
    if inp:
        p = inp.get("participants", {})
        parents = f", родителей: {p.get('parents_count')}" if p.get("parents_enabled") else ", без родителей"
        grade = f"{inp['grade']} класс" if inp.get("grade") else f"{inp.get('grade_group')} классы"
        out += [f"**{event_title or inp['event_id']}** · {grade} · {inp['pupils_count']} учеников{parents} · "
                f"{inp['duration_minutes']} минут · {FORMAT.get(inp['format'], inp['format'])}", ""]
    c = v["concept"]
    out += ["## Концепция", c["summary"], "", f"**Цель:** {c['goal']}", "", "**Задачи:**"]
    out += [f"- {t}" for t in c["tasks"]]
    out += ["", "**Результат:**"] + [f"- {t}" for t in c["expected_outcomes"]] + [""]
    out += ["## Роли", "| Роль | Кто | Сколько | Блоки |", "|---|---|---|---|"]
    for r in v["roles"]:
        out.append(f"| {r['title']} | {r['participant_type']}{' / ' + r['role_mode'] if r.get('role_mode') else ''} | {r['count']} | {', '.join(r['block_ids'])} |")
    out += ["", "## Сценарий"]
    for b in v["timeline"]:
        end = b["start_minute"] + b["duration_minutes"]
        out += ["", f"### {b['start_minute']}–{end} мин · {b['title']} ({b['duration_minutes']} мин)", f"*{b['purpose']}*", "",
                b["teacher_script"], "", "**Что делают ученики:**"] + [f"- {a}" for a in b["pupil_actions"]]
        if b["material_ids"]:
            out.append(f"\n**Материалы:** {', '.join(b['material_ids'])}")
    out += ["", "## Материалы"]
    for m in v["materials"]:
        flags = " · печать" if m["print_required"] else ""
        out += ["", f"### {m['title']} (`{m['material_id']}`, {m['type']}{flags})", "", m["content"].replace("\n", "  \n"), "",
                f"*Педагогу:* {m['teacher_notes']}"]
    plan = v.get("parent_participation_plan")
    if plan and plan.get("enabled"):
        out += ["", "## Участие родителей", f"Родителей: {plan['parents_count']} ({plan['parent_size_group']})"]
        out += [f"- {a['role_mode']}: {a['count']} - блоки {', '.join(a['block_ids'])}" for a in plan["assignments"]]
        if plan.get("voting"):
            vt = plan["voting"]
            out += [f"- Голосование: {vt.get('award_title') or 'без приза'}; критерий - {vt['criterion']}; ничья - {vt['tie_rule']}"]
        out += [f"- Если родители не придут: {plan['teacher_fallback']}"]
    out += ["", "## Подготовка и проведение"] + [f"- {t}" for t in v["teacher_instructions"]]
    if v.get("sources"):
        out += ["", "## Источники"] + [f"- {s['title']} - {s['publisher']} ({s['url']})" for s in v["sources"]]
    qr = v.get("quality_report")
    if qr:
        status = QUALITY_STATUS.get(qr["status"], qr["status"])
        out += ["", f"## Проверка качества: {status}"]
        for i in qr.get("issues", []):
            where = issue_place(v, i.get("location", ""))
            out.append(f"- {SEVERITY.get(i['severity'], i['severity'])}{' · ' + where if where else ''}: {i['message']} (`{i['code']}`)")
    return "\n".join(out) + "\n"