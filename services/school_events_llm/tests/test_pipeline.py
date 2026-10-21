import copy
import json
import tempfile
import unittest
from pathlib import Path

from app.generation.pipeline import Generator
from app.llm.fixture import FixtureLLM
from app.trace import RunTrace
from tests.helpers import EXAMPLE_NAMES, catalog, contract02_variant_keys, golden, minimal_request, request, settings


def run(raw, goldens, broken=None, run_dir=None, **kw):
    """Запускает полный конвейер генерации 1-3 вариантов и собирает внешний проект.

    Параметры:
        `raw`, `goldens`, `broken`, `run_dir`, `**kw`.
    """
    client = FixtureLLM(goldens, broken=broken)
    trace = RunTrace(run_dir, secrets=["sk-test-SECRET-123456"]) if run_dir else None
    gen = Generator(settings(), catalog(), client, trace=trace)
    return gen.run(raw, **kw), client


class PipelineTest(unittest.TestCase):
    def test_end_to_end_each_golden(self):
        """Проверяет сценарий теста: end to end each golden."""
        for name in EXAMPLE_NAMES:
            with self.subTest(name=name):
                outcome, _ = run(request(name), [golden(name)])
                self.assertEqual(outcome.project["status"], "completed", [o.issues for o in outcome.variants])
                variant = outcome.project["variants"][0]
                self.assertEqual(sum(b["duration_minutes"] for b in variant["timeline"]), outcome.normalized.duration_minutes)
                self.assertTrue(set(variant) <= contract02_variant_keys())
                self.assertEqual(variant["quality_report"]["status"], "passed")

    def test_t028_per_block_mode_for_60_minutes(self):
        """Проверяет сценарий теста: t028 per block mode for 60 minutes."""
        outcome, client = run(request("ex3_labour_day"), [golden("ex3_labour_day")])
        tasks = [c["task"] for c in client.calls]
        self.assertEqual(tasks.count("scenario_block"), 6)
        self.assertNotIn("scenario_blocks", tasks)
        self.assertEqual(outcome.project["status"], "completed")

    def test_t018_t047_broken_json_repaired_and_traced(self):
        """Проверяет сценарий теста: t018 t047 broken json repaired and traced."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            outcome, client = run(request("ex1_knowledge_day"), [golden("ex1_knowledge_day")],
                                  broken={"scenario_plan": 1, "materials": 1}, run_dir=run_dir)
            self.assertEqual(outcome.project["status"], "completed")
            manifests = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((run_dir / "calls").glob("*/manifest.json"))]
            plan_calls = [m for m in manifests if m["stage"] == "scenario_plan"]
            self.assertEqual([m["status"] for m in plan_calls], ["failed", "completed"])
            self.assertEqual(plan_calls[1]["parent_call_id"], plan_calls[0]["call_id"])
            self.assertEqual(len({m["call_id"] for m in manifests}), len(manifests))
            for f in ("input.json", "normalized_request.json", "concepts.json", "final_result.json", "metadata.json",
                      "events.jsonl", "variants/v1/variant_package.json"):
                self.assertTrue((run_dir / f).is_file(), f)
            for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines():
                json.loads(line)
            call_dir = run_dir / "calls" / plan_calls[1]["call_id"]
            for f in ("messages.json", "prompt.md", "response.raw.txt", "response.parsed.json"):
                self.assertTrue((call_dir / f).is_file(), f)

    def test_t016_partial_when_variant_fails(self):
        """Проверяет сценарий теста: t016 partial when variant fails."""
        g_ok = golden("ex1_knowledge_day")
        g_bad = copy.deepcopy(g_ok)
        g_bad["concept"]["title"] = "Другая концепция"
        g_bad["concept"]["primary_mechanic"] = "team_game"
        g_bad["concept"]["key_activities"] = [{"activity_type": "game", "description": "игра"}]
        g_bad["variant_package"]["variant"]["concept"]["values_to_mechanics"] = g_bad["variant_package"]["variant"]["concept"]["values_to_mechanics"][:1]
        raw = request("ex1_knowledge_day")
        raw["generation"]["variants_count"] = 2
        outcome, _ = run(raw, [g_ok, g_bad])
        self.assertEqual(outcome.project["status"], "partial")
        self.assertEqual(outcome.project["completed_variants"], 1)
        self.assertEqual([v.status for v in outcome.variants], ["completed", "failed"])

    def test_t015_identical_concepts_detected(self):
        """Проверяет сценарий теста: t015 identical concepts detected."""
        raw = request("ex1_knowledge_day")
        raw["generation"]["variants_count"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            outcome, client = run(raw, [golden("ex1_knowledge_day"), golden("ex1_knowledge_day")], run_dir=Path(tmp) / "r")
            self.assertGreater([c["task"] for c in client.calls].count("variation_plan"), 1)
            checks = json.loads((Path(tmp) / "r" / "concepts.json").read_text(encoding="utf-8"))["checks"]
            self.assertTrue(any(c["code"].startswith("DIV-") for c in checks))

    def test_t104_universal_mode_runs(self):
        """Проверяет сценарий теста: t104 universal mode runs."""
        outcome, _ = run(request("ex2_mothers_day"), [golden("ex2_mothers_day")], context_mode="universal")
        self.assertEqual(outcome.normalized.context_mode, "universal")
        self.assertEqual(outcome.project["status"], "completed")

    def test_t065_secrets_not_in_trace(self):
        """Проверяет сценарий теста: t065 secrets not in trace."""
        raw = minimal_request(teacher_preferences={"notes": "ключ sk-test-SECRET-123456 случайно вставлен"})
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run(raw, [golden("ex1_knowledge_day")], run_dir=run_dir)
            for path in run_dir.rglob("*"):
                if path.is_file():
                    self.assertNotIn("sk-test-SECRET-123456", path.read_text(encoding="utf-8"), path)



class TokenBudgetTest(unittest.TestCase):
    def test_variation_plan_limit_fits_concepts(self):
        """Лимит variation_plan растёт с числом вариантов и вмещает концепции эталонного объёма."""
        generator = Generator(settings(), catalog(), FixtureLLM([golden("ex1_knowledge_day")]))
        concepts = [golden(name)["concept"] for name in EXAMPLE_NAMES]
        for count in (1, 2, 3):
            with self.subTest(variants=count):
                raw = request("ex1_knowledge_day")
                raw["generation"]["variants_count"] = count
                from app.normalize import normalize
                n = normalize(raw, catalog(), settings())
                limit = generator.max_output_tokens("variation_plan", n)
                chars = sum(len(json.dumps(c, ensure_ascii=False, indent=2)) for c in concepts[:count]) + 150
                # консервативная оценка для кириллицы: 2.5 символа на токен
                self.assertGreaterEqual(limit, int(chars / 2.5), f"limit={limit}, chars={chars}")
        self.assertEqual(generator.max_output_tokens("scenario_plan", n), settings().generation()["tasks"]["scenario_plan"]["max_output_tokens"])


if __name__ == "__main__":
    unittest.main()