"""Объём реплик педагога зависит от длительности блока.

Раньше порог был один на любой блок (600 символов при detailed): трёхминутное приветствие
считалось коротким наравне с двадцатиминутной работой в командах.
"""

import unittest

from app.generation.pipeline import Generator
from app.llm.fixture import FixtureLLM
from app.normalize import normalize
from app.prompting.composer import Composer
from app.script_length import script_min_chars, script_target_chars
from tests.helpers import catalog, golden, request, settings
from tests.test_validation_render import codes, setup


def gen_cfg():
    return settings().generation()


class ScriptLengthTest(unittest.TestCase):
    def test_grows_with_duration(self):
        """Длинному блоку нужно больше текста, чем короткому; детальный сценарий длиннее стандартного."""
        cfg = gen_cfg()
        self.assertLess(script_min_chars(cfg, "detailed", 3), script_min_chars(cfg, "detailed", 20))
        self.assertLess(script_min_chars(cfg, "standard", 10), script_min_chars(cfg, "detailed", 10))
        self.assertLess(script_min_chars(cfg, "brief", 10), script_min_chars(cfg, "standard", 10))
        self.assertGreater(script_target_chars(cfg, "detailed", 10), script_min_chars(cfg, "detailed", 10))

    def test_warning_depends_on_block_duration(self):
        """Один и тот же текст достаточен для короткого блока и мал для длинного."""
        n, v = setup("ex1_knowledge_day")
        cfg = gen_cfg()
        short, long_ = v["timeline"][0], v["timeline"][2]
        text = "Х" * (script_min_chars(cfg, "detailed", short["duration_minutes"]) + 10)
        self.assertLess(len(text), script_min_chars(cfg, "detailed", long_["duration_minutes"]))
        short["teacher_script"] = text
        self.assertNotIn("SCRIPT-SHORT", codes(v, n))
        long_["teacher_script"] = text
        self.assertIn("SCRIPT-SHORT", codes(v, n))

    def test_prompts_name_the_size(self):
        """Промпт блоков называет объём; в плане для этапа блоков объём указан у каждого блока."""
        n = normalize(request("ex1_knowledge_day"), catalog(), settings())
        composed = Composer(settings(), catalog()).compose(
            "scenario_block", n, stage_input="",
            output_vars={"variant_id": "v1", "block_id": "block_02", "start_minute": "5", "block_minutes": "15"})
        text = "\n".join(m["content"] for m in composed.messages)
        self.assertIn(f"на 15 мин - от {script_min_chars(gen_cfg(), 'detailed', 15)}", text)
        plan = {"variant_id": "v1", "title": "T", "concept": {"summary": "s", "goal": "g", "values_to_mechanics": []},
                "roles": [], "blocks": [{"block_id": "block_01", "title": "A", "purpose": "p", "role_ids": [], "planned_material_ids": []}],
                "planned_materials": [], "grouping_request": {"block_ids": []}}
        plan_text = Generator.plan_text(plan, [(0, 10)], ("whole_class", [27]), script_chars=lambda m: f"от {m * 100}")
        self.assertIn("реплики педагога: от 1000", plan_text)


class PerBlockModeTest(unittest.TestCase):
    def test_blocks_written_one_by_one(self):
        """Блоки пишутся по одному вызову и для 45 минут: у каждого блока свой запрос и свой лимит ответа."""
        client = FixtureLLM([golden("ex1_knowledge_day")])
        outcome = Generator(settings(), catalog(), client).run(request("ex1_knowledge_day"))
        tasks = [c["task"] for c in client.calls]
        self.assertNotIn("scenario_blocks", tasks)
        self.assertEqual(tasks.count("scenario_block"), len(outcome.project["variants"][0]["timeline"]))
        self.assertEqual(outcome.project["status"], "completed")


if __name__ == "__main__":
    unittest.main()