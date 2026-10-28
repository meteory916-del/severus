# -*- coding: utf-8 -*-
"""Рендер всех E2E-прогонов в читаемый Markdown."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SERVICE = Path("services/school_events_llm")
OUT = Path("qa/docs/review/generated")
CASES = [
    ("E2E-01", "job_6b4781f4be114d1ba0fd382699e2ed19", "knowledge_day_6_45"),
    ("E2E-02", "job_37b888b5cc174d22913e943720796655", "knowledge_day_2_30"),
    ("E2E-03", "job_d324c4d4d56446258672436a05e8640f", "victory_day_10_90"),
    ("E2E-04", "job_4fc18475afe149a1b1c904aacc7f8c67", "mothers_day_45"),
    ("E2E-05", "job_d1ea0b7bf0ad481fa3e2a2d686fd607a", "teachers_day_45"),
    ("E2E-06", "job_31e9ea5aa2ee478bb99199fda1604c57", "knowledge_day_60_school"),
    ("E2E-07", "job_b573d36c2eab4bfe9886c796954088c1", "unity_day_60"),
    ("E2E-08", "job_95ba6b9897e64ae38121e5aad371f439", "teachers_day_30_min"),
    ("E2E-09", "job_ea5a1d8c18594b35904e75963ce4324b", "new_year_45"),
    ("E2E-10", "job_3c352a56bfc04d6eb7ad4e3304fefaad", "knowledge_day_8_30"),
    ("E2E-11", "job_fc8452eac03c49dcb5b2f7472b046fee", "last_bell_11_45"),
    ("E2E-12", "job_13304ddd5a744f2c9eb30469cf6cfbf3", "womens_day_45"),
    ("E2E-13", "job_dd42e6b8c4c84be18f7551be61727271", "christmas_45"),
    ("E2E-14", "job_05e495e03ddc4eb29b7108dbc890e2cc", "defender_day_60"),
    ("E2E-15", "job_229eb84b84884f3e9473493dcc784ed1", "graduation_60"),
    ("E2E-16", "job_953464af28db49eebb1718329a38bf7f", "labour_day_60"),
    ("E2E-17", "job_e4ac351c0ac641e9b36b8c709b2bd8f3", "middle_urals_45"),
    ("E2E-18", "job_f237da9c33c9416c9b0acff0de219f9b", "sverdlovsk_oblast_30"),
]

OUT.mkdir(parents=True, exist_ok=True)
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
for case_id, job_id, name in CASES:
    package = f"data/runs/{job_id}/variants/v1/variant_package.json"
    request = f"data/runs/{job_id}/input.json"
    result = subprocess.run(
        [sys.executable, "-m", "app", "render", package, "--request", request, "--markdown"],
        cwd=SERVICE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    if result.returncode != 0:
        print(case_id, "FAILED", result.stderr[:300])
        continue
    target = OUT / f"{case_id}_{name}.md"
    target.write_text(result.stdout, encoding="utf-8")
    print(case_id, target, len(result.stdout.splitlines()), "lines")
