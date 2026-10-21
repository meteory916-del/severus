import contextlib
import json
import io
import unittest

from app.cli import main
from app.sources import check_sources
from tests.helpers import EXAMPLES, settings


class CliModeTest(unittest.TestCase):
    def test_public_generate_does_not_accept_experiment_flags(self):
        """Проверяет сценарий теста: public generate does not accept experiment flags."""
        request_path = str(EXAMPLES / "requests" / "ex1_knowledge_day.json")
        stderr = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(stderr):
            main(["generate", request_path, "--context-mode", "universal"])
        self.assertIn("--context-mode", stderr.getvalue())

    def test_experiment_command_runs_universal_fixture(self):
        """Проверяет сценарий теста: experiment command runs universal fixture."""
        request_path = str(EXAMPLES / "requests" / "ex2_mothers_day.json")
        golden_path = str(EXAMPLES / "golden" / "ex2_mothers_day.json")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main([
                "experiment",
                request_path,
                "--context-mode",
                "universal",
                "--fixture",
                golden_path,
                "--no-trace",
            ])
        self.assertEqual(code, 0)
        summary = json.loads(stdout.getvalue())
        self.assertEqual(summary["context_mode"], "universal")


class SourcesCheckTest(unittest.TestCase):
    def test_sources_check_reports_coverage_for_empty_pilot_corpus(self):
        """Проверяет сценарий теста: sources check reports coverage for empty pilot corpus."""
        report = check_sources(settings())
        self.assertIn("coverage", report)
        self.assertEqual(report["verified_fragments"], 0)
        self.assertFalse(report["coverage"]["region_RU_SVE"]["covered"])


if __name__ == "__main__":
    unittest.main()