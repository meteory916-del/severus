"""Списки в ответе модели: действия учеников и пункты подготовки.

Регрессия по второму прогону GigaChat-2-Max (2026-10-26):
- в каждом блоке одно действие учеников вместо 2-5 (пример в промпте показывал один пункт);
- пункт подготовки пришёл как «1. Подготовьте…», в сценарии получалось «- 1. Подготовьте…»;
- первый ответ плана не прошёл схему, сервис сам повторил запрос.
"""

import json
import tempfile
import unittest
from pathlib import Path

from app.generation.pipeline import strip_list_markers
from app.markdown import variant_to_markdown
from app.trace import RunTrace
from tests.helpers import ROOT, catalog, settings
from tests.test_material_ids import ReplayLLM, replay_generator
from tests.test_validation_render import codes, setup

REPLAY_DIR = ROOT / "tests" / "fixtures" / "replay_gigachat_roles"


class StripListMarkersTest(unittest.TestCase):
    def test_markers_removed(self):
        """Номера и маркеры в начале пункта убираются."""
        items = ["1. Подготовьте карточки", "2) Раздайте бланки", "- Проверьте проектор", "• Расставьте столы"]
        self.assertEqual(strip_list_markers(items), ["Подготовьте карточки", "Раздайте бланки", "Проверьте проектор", "Расставьте столы"])

    def test_text_with_numbers_untouched(self):
        """Числа, которые относятся к тексту, не трогаются."""
        items = ["5 групп: 6, 6, 5, 5, 5", "2.5 минуты на обсуждение", "1-4 классы - отдельно"]
        self.assertEqual(strip_list_markers(items), items)

    def test_empty_items_dropped(self):
        """Пустые пункты отбрасываются, но список целиком не пропадает."""
        self.assertEqual(strip_list_markers(["1. Раз", "  ", "- "]), ["Раз"])
        self.assertEqual(strip_list_markers(["- "]), ["-"])


class PupilActionsCheckTest(unittest.TestCase):
    def test_single_action_is_warning(self):
        """Одно действие учеников в блоке - предупреждение."""
        n, v = setup("ex1_knowledge_day")
        v["timeline"][0]["pupil_actions"] = v["timeline"][0]["pupil_actions"][:1]
        self.assertIn("PUPIL-ACTIONS-FEW", codes(v, n))


class ReplaySecondRunTest(unittest.TestCase):
    def test_gigachat_second_run(self):
        """Записанный второй прогон GigaChat: повтор плана, досборка ролей, очистка списков, предупреждения."""
        raw = json.loads((REPLAY_DIR / "request.json").read_text(encoding="utf-8"))
        client = ReplayLLM(REPLAY_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            outcome = replay_generator(client, trace=RunTrace(run_dir, full_prompts=False, full_responses=False, secrets=[])).run(raw)
        self.assertEqual(outcome.project["status"], "completed")
        self.assertEqual(client.calls, ["variation_plan", "scenario_plan", "scenario_plan", "scenario_blocks", "materials"])

        result = outcome.project["variants"][0]
        all_blocks = [b["block_id"] for b in result["timeline"]]
        for role in result["roles"]:
            self.assertEqual(role["block_ids"], all_blocks, role["role_id"])
        self.assertEqual(result["parent_participation_plan"]["voting"]["voters_count_planned"], 10)
        self.assertEqual({m["type"] for m in result["materials"]}, {"parent_instruction", "audience_ballot", "award_instruction"})

        self.assertIn("Подготовьте карточки с номерами команд для распределения детей по группам.", result["teacher_instructions"])
        for item in result["teacher_instructions"]:
            self.assertFalse(item[:1].isdigit(), item)

        issues = result["quality_report"]["issues"]
        self.assertEqual({i["severity"] for i in issues}, {"warning"})
        few = [i["location"] for i in issues if i["code"] == "PUPIL-ACTIONS-FEW"]
        self.assertEqual(few, [f"timeline.{bid}" for bid in all_blocks])

        # В читаемом сценарии замечание называет блок, а не только код проверки.
        md = variant_to_markdown(result, outcome.project["input"], "День знаний")
        first = result["timeline"][0]
        self.assertIn("## Проверка качества: есть замечания", md)
        self.assertIn(f"- Замечание · блок «{first['title']}» (0-{first['duration_minutes']} мин): Действий учеников меньше двух (1) (`PUPIL-ACTIONS-FEW`)", md)


if __name__ == "__main__":
    unittest.main()