# -*- coding: utf-8 -*-
"""Ручной E2E-прогон по API против живого Backend в режиме llm_service.

Перед запуском:
    cd services/school_events_llm; LLM_SERVICE_FIXTURE_MODE=true python -m app serve
    GENERATOR_MODE=llm_service python -m uvicorn backend.main:app --port 8000

Ограничение fixture-режима: HTTP-клиент берёт эталон по порядку, а не по event_id,
поэтому без реальной модели проходят только запросы, совпадающие с первым эталоном.
Результаты по остальным событиям в fixture-режиме недействительны.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
INPUTS = sorted(Path("qa/tests/fixtures/inputs").glob("*.json"))
NEGATIVES = {
    "unknown_event": {
        "event_id": "ural_culture", "region_id": "RU-SVE", "grade_group": "5-8",
        "pupils_count": 20, "duration_minutes": 45, "format": "class_hour",
    },
    "wrong_format": {
        "event_id": "last_bell", "region_id": "RU-SVE", "grade_group": "5-8",
        "pupils_count": 20, "duration_minutes": 45, "format": "interactive_lesson",
    },
}


def wait_job(client: httpx.Client, status_url: str, timeout: float = 120.0) -> dict:
    """Ждёт терминальный статус задания, чтобы не проверять промежуточный running."""
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = client.get(BASE + status_url).json()
        if last.get("status") in {"completed", "partial", "failed", "blocked"}:
            return last
        time.sleep(0.5)
    return last


def summarize(project: dict) -> dict:
    """Собирает минимальные проверки, которые нужны приёмке."""
    variants = project.get("variants") or []
    result = {"project_status": project.get("status"), "variants": len(variants), "checks": []}
    for variant in variants:
        timeline = variant.get("timeline") or []
        quality = variant.get("quality_report") or {}
        result["checks"].append({
            "id": variant.get("variant_id"),
            "blocks": len(timeline),
            "sum_min": sum(b.get("duration_minutes", 0) for b in timeline),
            "start_zero": bool(timeline) and timeline[0].get("start_minute") == 0,
            "scripts_ok": all((b.get("teacher_script") or "").strip() for b in timeline),
            "quality_status": quality.get("status"),
            "issues": [
                {"code": i.get("code"), "severity": i.get("severity")}
                for i in (quality.get("issues") or [])
            ],
        })
    return result


def main() -> None:
    rows: list[dict] = []
    with httpx.Client(timeout=120) as client:
        for path in INPUTS:
            request = json.loads(path.read_text(encoding="utf-8"))
            row: dict = {"case": path.name}
            try:
                response = client.post(BASE + "/api/v1/generations", json=request)
                row["http"] = response.status_code
                if response.status_code != 202:
                    row["error"] = response.text[:300]
                    rows.append(row)
                    continue
                accepted = response.json()
                job = wait_job(client, accepted["status_url"])
                project = client.get(BASE + accepted["project_url"]).json()
                row.update(summarize(project))
                row["job_status"] = job.get("status")
                row["job_errors"] = job.get("errors")
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)

        for name, request in NEGATIVES.items():
            response = client.post(BASE + "/api/v1/generations", json=request)
            rows.append({"case": name, "http": response.status_code, "body": response.text[:300]})

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
