import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.settings import Settings
from app.sources import check_sources
from tests.helpers import ROOT


class SourcesCorpusValidationTest(unittest.TestCase):
    """Проверяет структурную валидацию локального корпуса проверенных источников."""

    def test_t103_duplicate_ids_and_missing_verifier_are_errors(self):
        """Проверяет T-103: дубликаты ID и verified-фрагмент без проверяющего блокируют корпус.

        Тест создает временный минимальный корень сервиса, копирует каталог событий и
        справочники, затем подменяет корпус RU-SVE заведомо ошибочными данными. После
        проверки ожидаются ошибки дублирования source_id, fragment_id и отсутствия
        verified_by. Дополнительно проверяется, что отчет покрытия формируется даже
        при структурных ошибках корпуса.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "catalog" / "events", root / "catalog" / "events")
            shutil.copy2(ROOT / "catalog" / "values.json", root / "catalog" / "values.json")
            shutil.copy2(ROOT / "catalog" / "dependencies.json", root / "catalog" / "dependencies.json")
            region_dir = root / "catalog" / "regions" / "RU-SVE"
            region_dir.mkdir(parents=True)

            corpus = {
                "schema_version": "1.0",
                "region_id": "RU-SVE",
                "sources": [
                    {"source_id": "source_dup", "title": "Источник 1"},
                    {"source_id": "source_dup", "title": "Источник 2"},
                ],
                "fragments": [
                    {
                        "fragment_id": "fragment_dup",
                        "source_id": "source_dup",
                        "quote": "Проверяемый фрагмент для теста.",
                        "verification_status": "verified",
                        "collected_by": "collector_1",
                        "regions": ["RU-SVE"],
                        "events": ["knowledge_day"],
                        "topics": [],
                    },
                    {
                        "fragment_id": "fragment_dup",
                        "source_id": "source_dup",
                        "quote": "Второй фрагмент с повторяющимся идентификатором.",
                        "verification_status": "draft",
                        "regions": ["RU-SVE"],
                        "events": ["knowledge_day"],
                        "topics": [],
                    },
                ],
            }
            (region_dir / "verified_sources.json").write_text(
                json.dumps(corpus, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            report = check_sources(Settings(root=root, env={}))
            codes = {item["code"] for item in report["issues"]}

            self.assertEqual(report["status"], "error")
            self.assertIn("SOURCE-DUPLICATE", codes)
            self.assertIn("FRAGMENT-DUPLICATE", codes)
            self.assertIn("FRAGMENT-VERIFIER", codes)
            self.assertIn("coverage", report)
            self.assertIn("knowledge_day", report["coverage"]["events"])

    def test_fragment_must_reference_known_source(self):
        """Фрагмент без source_id или со ссылкой на отсутствующий источник - ошибка корпуса."""
        fragment = {
            "quote": "Проверяемый фрагмент для теста.",
            "verification_status": "verified",
            "collected_by": "collector_1",
            "verified_by": "verifier_1",
            "regions": ["RU-SVE"],
            "events": ["knowledge_day"],
            "topics": [],
        }
        corpus = {
            "schema_version": "1.0",
            "region_id": "RU-SVE",
            "sources": [{"source_id": "source_ok", "title": "Источник"}],
            "fragments": [
                {**fragment, "fragment_id": "fragment_ok", "source_id": "source_ok"},
                {**fragment, "fragment_id": "fragment_unknown", "source_id": "source_missing"},
                {**fragment, "fragment_id": "fragment_no_source"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "catalog" / "events", root / "catalog" / "events")
            region_dir = root / "catalog" / "regions" / "RU-SVE"
            region_dir.mkdir(parents=True)
            (region_dir / "verified_sources.json").write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")

            report = check_sources(Settings(root=root, env={}))
            by_location = {(item["code"], item["location"]) for item in report["issues"]}

            self.assertEqual(report["status"], "error")
            self.assertIn(("FRAGMENT-SOURCE-UNKNOWN", "fragments[1]"), by_location)
            self.assertIn(("FRAGMENT-SOURCE-MISSING", "fragments[2]"), by_location)
            self.assertFalse(any(location == "fragments[0]" for _, location in by_location))


if __name__ == "__main__":
    unittest.main()