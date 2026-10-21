import copy
import unittest

from app.contracts.llm import VariantPackage
from app.normalize import normalize
from app.render import render_variant
from app.validation.checks import report_status, validate_variant
from tests.helpers import EXAMPLE_NAMES, catalog, contract02_variant_keys, golden, request, settings


def setup(name):
    """Подготавливает нормализованный запрос и внутренний вариант для тестовой проверки.

    Параметры:
        `name`.
    """
    n = normalize(request(name), catalog(), settings())
    v = VariantPackage.model_validate(golden(name)["variant_package"]).model_dump()["variant"]
    return n, v


def codes(v, n):
    """Возвращает множество кодов проблем, найденных валидатором.

    Параметры:
        `v`, `n`.
    """
    return {i.code for i in validate_variant(v, n, catalog(), settings().generation())}


class GoldenTest(unittest.TestCase):
    def test_goldens_pass_all_checks(self):
        """Проверяет сценарий теста: goldens pass all checks."""
        for name in EXAMPLE_NAMES:
            with self.subTest(name=name):
                n, v = setup(name)
                issues = validate_variant(v, n, catalog(), settings().generation())
                self.assertEqual(report_status(issues), "passed", [i.to_dict() for i in issues])


class MutationTest(unittest.TestCase):
    def test_timing_sum(self):
        """Проверяет сценарий теста: timing sum."""
        n, v = setup("ex1_knowledge_day")
        v["timeline"][-1]["duration_minutes"] += 1
        self.assertIn("TIME-GRID", codes(v, n))

    def test_t012_parent_roles_when_disabled(self):
        """Проверяет сценарий теста: t012 parent roles when disabled."""
        n, v = setup("ex2_mothers_day")
        v["roles"].append({"role_id": "parent_x", "participant_type": "parent", "role_mode": "helper", "title": "x", "count": 1, "block_ids": ["block_01"]})
        self.assertIn("PARENTS-DISABLED", codes(v, n))

    def test_t036_simultaneous_parents(self):
        """Проверяет сценарий теста: t036 simultaneous parents."""
        n, v = setup("ex1_knowledge_day")
        v["roles"][3]["count"] = 11  # 2 помощника + 11 зрителей > 12
        self.assertIn("PARENTS-OVER", codes(v, n))

    def test_group_work_false(self):
        """Проверяет сценарий теста: group work false."""
        n, v = setup("ex2_mothers_day")
        v["pupil_grouping"] = {"total_pupils": 20, "mode": "small_groups", "group_sizes": [5, 5, 5, 5], "block_ids": ["block_03"]}
        v["timeline"][2]["teacher_script"] += " Разделите класс на 4 группы."
        got = codes(v, n)
        self.assertIn("GROUP-WORK-FORBIDDEN", got)

    def test_group_sum(self):
        """Проверяет сценарий теста: group sum."""
        n, v = setup("ex1_knowledge_day")
        v["pupil_grouping"]["group_sizes"] = [6, 6, 5, 5]
        self.assertIn("GROUP-SUM", codes(v, n))

    def test_t010_t011_resources(self):
        """Проверяет сценарий теста: t010 t011 resources."""
        n, v = setup("ex3_labour_day")
        v["materials"][1]["print_required"] = True
        v["materials"][1]["dependencies"].append("printer")
        got = codes(v, n)
        self.assertIn("PRINT-UNAVAILABLE", got)
        self.assertIn("RESOURCE-UNAVAILABLE", got)

    def test_t097_dependency_vocabulary(self):
        """Проверяет сценарий теста: t097 dependency vocabulary."""
        n, v = setup("ex1_knowledge_day")
        v["materials"][1]["dependencies"].append("3d_printer")
        self.assertIn("DEP-UNKNOWN", codes(v, n))

    def test_t090_family_task_without_alternative(self):
        """Проверяет сценарий теста: t090 family task without alternative."""
        n, v = setup("ex2_mothers_day")
        m = next(x for x in v["materials"] if x.get("family_task"))
        m["content"] = "Спроси дома у мамы, какое у неё любимое занятие, и запомни ответ."
        self.assertIn("VAL-005", codes(v, n))

    def test_t086_missing_value(self):
        """Проверяет сценарий теста: t086 missing value."""
        n, v = setup("ex1_knowledge_day")
        v["concept"]["values_to_mechanics"] = v["concept"]["values_to_mechanics"][:1]
        self.assertIn("VAL-001", codes(v, n))

    def test_t099_fact_without_verified_fragment(self):
        """Проверяет сценарий теста: t099 fact without verified fragment."""
        n, v = setup("ex1_knowledge_day")
        v["fact_claims"] = [{"claim_id": "fc_01", "text": "Праздник учреждён давно", "location": "timeline.block_01.teacher_script",
                             "source_id": "src_fake", "fragment_id": "frag_fake", "needs_teacher_check": False}]
        self.assertIn("FACT-SOURCE", codes(v, n))

    def test_t101_unregistered_year(self):
        """Проверяет сценарий теста: t101 unregistered year."""
        n, v = setup("ex1_knowledge_day")
        v["timeline"][0]["teacher_script"] += " Этот праздник появился в 1984 году."
        self.assertIn("FACT-UNREGISTERED", codes(v, n))

    def test_t102_needs_teacher_check_is_warning(self):
        """Проверяет сценарий теста: t102 needs teacher check is warning."""
        n, v = setup("ex1_knowledge_day")
        v["fact_claims"] = [{"claim_id": "fc_01", "text": "утверждение", "location": "timeline.block_01", "needs_teacher_check": True}]
        issues = validate_variant(v, n, catalog(), settings().generation())
        self.assertEqual(report_status(issues), "warning")

    def test_ballot_not_allowed_without_vote(self):
        """Проверяет сценарий теста: ballot not allowed without vote."""
        n, v = setup("ex3_labour_day")
        v["materials"].append({**copy.deepcopy(v["materials"][0]), "material_id": "ballot_x", "type": "audience_ballot"})
        self.assertIn("BALLOT-NOT-ALLOWED", codes(v, n))


class RenderTest(unittest.TestCase):
    def test_t082_whitelist_matches_contract_02(self):
        """Проверяет сценарий теста: t082 whitelist matches contract 02."""
        allowed = contract02_variant_keys()
        for name in EXAMPLE_NAMES:
            with self.subTest(name=name):
                n, v = setup(name)
                out = render_variant(v, n, catalog(), [])
                self.assertTrue(set(out) <= allowed, set(out) - allowed)
                self.assertEqual(set(out["concept"]), {"summary", "goal", "tasks", "expected_outcomes"})
                for m in out["materials"]:
                    self.assertNotIn("family_task", m)
                keys = set()

                def walk(node):
                    """Рекурсивно преобразует вложенную структуру JSON Schema.

                    Параметры:
                        `node`.
                    """
                    if isinstance(node, dict):
                        keys.update(node)
                        for value in node.values():
                            walk(value)
                    elif isinstance(node, list):
                        for value in node:
                            walk(value)
                walk(out)
                for internal in ("values_to_mechanics", "pupil_grouping", "fact_claims", "family_task", "differs_from"):
                    self.assertNotIn(internal, keys)

    def test_t085_values_rendered_in_tasks(self):
        """Проверяет сценарий теста: t085 values rendered in tasks."""
        n, v = setup("ex1_knowledge_day")
        tasks = render_variant(v, n, catalog(), [])["concept"]["tasks"]
        self.assertTrue(tasks[0].startswith("Воспитательная задача:"))
        self.assertTrue(any(t.startswith("Ценность «Взаимопомощь» → командная задача") for t in tasks))

    def test_groups_rendered_in_role_title(self):
        """Проверяет сценарий теста: groups rendered in role title."""
        n, v = setup("ex1_knowledge_day")
        roles = render_variant(v, n, catalog(), [])["roles"]
        self.assertEqual(roles[1]["title"], "Учащиеся (5 групп: 6, 6, 5, 5, 5)")
        self.assertNotIn("role_mode", roles[0])

    def test_family_task_instruction(self):
        """Проверяет сценарий теста: family task instruction."""
        n, v = setup("ex2_mothers_day")
        out = render_variant(v, n, catalog(), [])
        self.assertNotIn("parent_participation_plan", out)
        self.assertTrue(any("необязательное" in x for x in out["teacher_instructions"]))


if __name__ == "__main__":
    unittest.main()