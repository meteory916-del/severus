"""Подсчёт токенов и журнал прогонов `data/runs/runs.jsonl`."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from app.cli import main
from app.llm.client import LLMError, LLMResult
from app.trace import RunTrace
from app.usage import TokenTally
from tests.helpers import EXAMPLES, ROOT
from tests.test_material_ids import ReplayLLM, replay_generator

REPLAY_DIR = ROOT / "tests" / "fixtures" / "replay_gigachat_no_schema"


class ReplayWithUsage(ReplayLLM):
    """Записанные ответы плюс `usage`, как его возвращает провайдер: 100 токенов на вход, 10 на выход."""

    def generate(self, **kwargs) -> LLMResult:
        result = super().generate(**kwargs)
        result.usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        return result


class BrokenLLM(ReplayLLM):
    def generate(self, **kwargs) -> LLMResult:
        raise LLMError("MODEL_UNAVAILABLE", "Модель недоступна")


def run_with_trace(client, tmp: str):
    run_dir = Path(tmp) / "runs" / "job_test"
    gen = replay_generator(client, trace=RunTrace(run_dir, full_prompts=False, full_responses=False, secrets=[]))
    raw = json.loads((REPLAY_DIR / "request.json").read_text(encoding="utf-8"))
    return gen, run_dir, raw


class TokenTallyTest(unittest.TestCase):
    def test_sums_by_stage(self):
        """Вход и выход складываются по всем ответам и по этапам."""
        tally = TokenTally()
        tally.add("scenario_plan", {"prompt_tokens": 4000, "completion_tokens": 1000})
        tally.add("scenario_block", {"prompt_tokens": 3000, "completion_tokens": 500})
        tally.add("scenario_block", {"prompt_tokens": 3100, "completion_tokens": 600})
        self.assertEqual(tally.totals(), {"prompt": 10100, "completion": 2100, "total": 12200, "complete": True})
        self.assertEqual(tally.as_dict()["by_stage"]["scenario_block"], {"calls": 2, "prompt": 6100, "completion": 1100})

    def test_missing_usage_marks_incomplete(self):
        """Если провайдер не вернул usage, итог помечается неполным, а не считается нулём молча."""
        tally = TokenTally()
        tally.add("materials", None)
        self.assertFalse(tally.totals()["complete"])
        self.assertEqual(tally.as_dict()["calls_without_usage"], 1)


class RunLogTest(unittest.TestCase):
    def test_completed_run_is_logged(self):
        """Успешная генерация: токены в metadata.json и строка в runs.jsonl."""
        with tempfile.TemporaryDirectory() as tmp:
            gen, run_dir, raw = run_with_trace(ReplayWithUsage(REPLAY_DIR), tmp)
            outcome = gen.run(raw, job_id="job_test")
            metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
            lines = (run_dir.parent / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(outcome.tokens, {"prompt": 400, "completion": 40, "total": 440, "complete": True})
        self.assertEqual(metadata["tokens"]["total"], 440)
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual((record["job_id"], record["status"], record["llm_calls"], record["event_id"]),
                         ("job_test", "completed", 4, "knowledge_day"))
        self.assertEqual(record["tokens"]["by_stage"]["materials"], {"calls": 1, "prompt": 100, "completion": 10})
        self.assertIsNone(record["error"])

    def test_failed_run_is_logged(self):
        """Генерация, упавшая с ошибкой модели, тоже попадает в журнал - со статусом failed и кодом ошибки."""
        with tempfile.TemporaryDirectory() as tmp:
            gen, run_dir, raw = run_with_trace(BrokenLLM(REPLAY_DIR), tmp)
            with self.assertRaises(LLMError):
                gen.run(raw, job_id="job_test")
            record = json.loads((run_dir.parent / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"]["code"], "MODEL_UNAVAILABLE")

    def test_no_trace_no_log(self):
        """Без трассы (--no-trace) журнал не пишется."""
        gen = replay_generator(ReplayWithUsage(REPLAY_DIR))
        raw = json.loads((REPLAY_DIR / "request.json").read_text(encoding="utf-8"))
        self.assertEqual(gen.run(raw).tokens["total"], 440)

    def test_cli_summary_has_tokens(self):
        """В выводе generate есть итог токенов; в режиме эталонов провайдера нет, итог помечен неполным."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            main(["generate", str(EXAMPLES / "requests" / "ex1_knowledge_day.json"),
                  "--fixture", str(EXAMPLES / "golden" / "ex1_knowledge_day.json"), "--no-trace"])
        summary = json.loads(stdout.getvalue())
        self.assertEqual(set(summary["tokens"]), {"prompt", "completion", "total", "complete"})
        self.assertFalse(summary["tokens"]["complete"])


if __name__ == "__main__":
    unittest.main()