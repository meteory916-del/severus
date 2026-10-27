"""Роли участников по блокам и связанные с ними проверки.

Регрессия по реальному прогону GigaChat-2-Max (2026-10-26): в плане у каждого блока
была одна роль («главный»), роли родителей не попали ни в один блок, поэтому
в голосовании оказалось 0 зрителей, хотя в зале 10 родителей.
"""

import unittest

from app.generation.pipeline import complete_block_roles
from tests.test_validation_render import codes, setup


def plan_with(blocks_roles, roles):
    return {"roles": [{"role_id": rid, "participant_type": pt} for rid, pt in roles],
            "blocks": [{"block_id": f"block_{i:02d}", "role_ids": list(r)} for i, r in enumerate(blocks_roles, 1)]}


ROLES = [("teacher_1", "teacher"), ("pupils_all", "pupils_group"), ("parent_helpers", "parent"), ("parent_audience", "parent")]


class CompleteBlockRolesTest(unittest.TestCase):
    def test_teacher_and_pupils_in_every_block(self):
        """Педагог и все учащиеся добавляются в блоки, где модель указала только кого-то одного."""
        plan = plan_with([["teacher_1"], ["pupils_all"]], ROLES[:2])
        added = complete_block_roles(plan)
        self.assertEqual([b["role_ids"] for b in plan["blocks"]], [["teacher_1", "pupils_all"], ["pupils_all", "teacher_1"]])
        self.assertEqual(added, {"pupils_all": ["block_01"], "teacher_1": ["block_02"]})

    def test_unassigned_parent_role_gets_all_blocks(self):
        """Роль родителей, не указанная ни в одном блоке, присутствует во всех блоках."""
        plan = plan_with([["teacher_1"], ["teacher_1", "parent_helpers"]], ROLES)
        complete_block_roles(plan)
        self.assertIn("parent_audience", plan["blocks"][0]["role_ids"])
        self.assertIn("parent_audience", plan["blocks"][1]["role_ids"])

    def test_assigned_parent_role_is_not_spread(self):
        """Роль родителей, которую модель уже расставила по блокам, не добавляется в другие блоки."""
        plan = plan_with([["teacher_1"], ["teacher_1", "parent_helpers", "parent_audience"]], ROLES)
        complete_block_roles(plan)
        self.assertNotIn("parent_helpers", plan["blocks"][0]["role_ids"])
        self.assertNotIn("parent_audience", plan["blocks"][0]["role_ids"])

    def test_complete_plan_unchanged(self):
        """Полный план не меняется."""
        full = ["teacher_1", "pupils_all", "parent_helpers", "parent_audience"]
        plan = plan_with([full, full], ROLES)
        self.assertEqual(complete_block_roles(plan), {})


class RoleChecksTest(unittest.TestCase):
    def test_role_unused(self):
        """Роль без единого блока - предупреждение."""
        n, v = setup("ex1_knowledge_day")
        for b in v["timeline"]:
            b["role_ids"] = [r for r in b["role_ids"] if r != "parent_helpers"]
        self.assertIn("ROLE-UNUSED", codes(v, n))

    def test_voting_without_voters(self):
        """Голосование, в котором 0 зрителей, - предупреждение."""
        n, v = setup("ex1_knowledge_day")
        v["parent_participation_plan"]["voting"]["voters_count_planned"] = 0
        self.assertIn("VOTING-NO-VOTERS", codes(v, n))

    def test_missing_parent_and_award_instructions(self):
        """Нет памятки помощникам и инструкции к награждению - предупреждения."""
        n, v = setup("ex1_knowledge_day")
        dropped = {m["material_id"] for m in v["materials"] if m["type"] in ("parent_instruction", "award_instruction")}
        self.assertTrue(dropped)
        v["materials"] = [m for m in v["materials"] if m["material_id"] not in dropped]
        for b in v["timeline"]:
            b["material_ids"] = [mid for mid in b["material_ids"] if mid not in dropped]
        found = codes(v, n)
        self.assertIn("PARENT-INSTRUCTION", found)
        self.assertIn("AWARD-INSTRUCTION", found)


if __name__ == "__main__":
    unittest.main()