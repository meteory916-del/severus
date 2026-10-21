import unittest

from app.normalize import RequestError, normalize, parent_size_group, size_group
from tests.helpers import catalog, minimal_request, settings


def norm(raw, **kw):
    """Выполняет операцию `norm`, реализующую соответствующую часть логики текущего модуля.

    Параметры:
        `raw`, `**kw`.
    """
    return normalize(raw, catalog(), settings(), **kw)


class DefaultsTest(unittest.TestCase):
    def test_t071_full_v1_profile_when_preferences_missing(self):
        """Проверяет сценарий теста: t071 full v1 profile when preferences missing."""
        n = norm(minimal_request())
        tp = n.teacher_preferences
        self.assertEqual(tp["interaction_level"], "low")
        self.assertIs(tp["group_work"], False)
        self.assertEqual((tp["style"], tp["script_detail"], tp["difficulty"], tp["preparation_effort"]),
                         ("classic", "standard", "standard", "minimal"))

    def test_t072_only_notes_keeps_notes(self):
        """Проверяет сценарий теста: t072 only notes keeps notes."""
        n = norm(minimal_request(teacher_preferences={"notes": "Меньше монологов"}))
        self.assertEqual(n.teacher_preferences["notes"], "Меньше монологов")
        self.assertEqual(n.teacher_preferences["interaction_level"], "low")

    def test_t073_explicit_values_not_overwritten(self):
        """Проверяет сценарий теста: t073 explicit values not overwritten."""
        n = norm(minimal_request(teacher_preferences={"interaction_level": "high", "group_work": True}))
        self.assertEqual(n.teacher_preferences["interaction_level"], "high")
        self.assertIs(n.teacher_preferences["group_work"], True)

    def test_t074_strict_types(self):
        """Проверяет сценарий теста: t074 strict types."""
        for prefs in ({"group_work": 0}, {"interaction_level": None}, {"group_work": "false"}):
            with self.subTest(prefs=prefs), self.assertRaises(RequestError):
                norm(minimal_request(teacher_preferences=prefs))

    def test_t075_resources_unknown_stay_null(self):
        """Проверяет сценарий теста: t075 resources unknown stay null."""
        n = norm(minimal_request())
        self.assertEqual(n.unknown_resources, ["projector", "printer", "internet", "audio"])
        self.assertIsNone(n.resources["projector"])

    def test_t076_t078_participants_and_generation_defaults(self):
        """Проверяет сценарий теста: t076 t078 participants and generation defaults."""
        n = norm(minimal_request())
        self.assertEqual((n.teachers_count, n.parents_enabled, n.parents_count, n.parent_roles, n.parent_audience_engagement),
                         (1, False, 0, [], "none"))
        self.assertEqual((n.variants_count, n.language), (1, "ru"))

    def test_t079_effective_input_has_full_profile(self):
        """Проверяет сценарий теста: t079 effective input has full profile."""
        n = norm(minimal_request())
        self.assertIn("teacher_preferences", n.effective_input)
        self.assertEqual(n.effective_input["generation"]["variants_count"], 1)
        self.assertEqual(n.effective_input["grade_group"], "5-8")


class ParentsTest(unittest.TestCase):
    def test_t032_t077_enabled_requires_count(self):
        """Проверяет сценарий теста: t032 t077 enabled requires count."""
        for p in ({"parents_enabled": True}, {"parents_enabled": True, "parents_count": 0}):
            with self.subTest(p=p), self.assertRaises(RequestError):
                norm(minimal_request(participants=p))

    def test_t033_disabled_with_count(self):
        """Проверяет сценарий теста: t033 disabled with count."""
        with self.assertRaises(RequestError):
            norm(minimal_request(participants={"parents_enabled": False, "parents_count": 4}))

    def test_default_audience_role(self):
        """Проверяет сценарий теста: default audience role."""
        n = norm(minimal_request(participants={"parents_enabled": True, "parents_count": 3}))
        self.assertEqual(n.parent_roles, ["audience"])
        self.assertEqual(n.parent_size_group, "3-5")

    def test_t039_vote_requires_audience(self):
        """Проверяет сценарий теста: t039 vote requires audience."""
        with self.assertRaises(RequestError):
            norm(minimal_request(participants={"parents_enabled": True, "parents_count": 6, "parent_roles": ["helper"],
                                               "parent_audience_engagement": "vote"}))

    def test_t040_low_audience_warning_without_mode_change(self):
        """Проверяет сценарий теста: t040 low audience warning without mode change."""
        n = norm(minimal_request(participants={"parents_enabled": True, "parents_count": 1, "parent_roles": ["audience"],
                                               "parent_audience_engagement": "audience_award"}))
        self.assertEqual(n.parent_audience_engagement, "audience_award")
        self.assertIn("LOW_AUDIENCE_FOR_VOTING", [w.code for w in n.warnings])

    def test_t034_t035_parent_groups(self):
        """Проверяет сценарий теста: t034 t035 parent groups."""
        cases = {0: "none", 1: "1-2", 2: "1-2", 3: "3-5", 5: "3-5", 6: "6-10", 10: "6-10", 11: "11_plus", 12: "11_plus"}
        for count, group in cases.items():
            self.assertEqual(parent_size_group(count), group)


class OtherRulesTest(unittest.TestCase):
    def test_t005_t006_size_groups(self):
        """Проверяет сценарий теста: t005 t006 size groups."""
        self.assertEqual([size_group(x) for x in (12, 15, 16, 25, 26, 27, 35)],
                         ["up_to_15", "up_to_15", "from_16_to_25", "from_16_to_25", "from_26_to_35", "from_26_to_35", "from_26_to_35"])

    def test_t003_variants_out_of_range(self):
        """Проверяет сценарий теста: t003 variants out of range."""
        for count in (0, 4):
            with self.subTest(count=count), self.assertRaises(RequestError) as ctx:
                norm(minimal_request(generation={"variants_count": count}))
            self.assertEqual(ctx.exception.code, "INVALID_VARIANTS_COUNT")

    def test_t026_grade_conflict(self):
        """Проверяет сценарий теста: t026 grade conflict."""
        with self.assertRaises(RequestError):
            norm(minimal_request(grade_group="1-4", grade=9))

    def test_grade_group_from_grade(self):
        """Проверяет сценарий теста: grade group from grade."""
        raw = minimal_request(grade=10)
        raw.pop("grade_group")
        self.assertEqual(norm(raw).age_group, "9-11")

    def test_t083_contract_not_extended(self):
        """Проверяет сценарий теста: t083 contract not extended."""
        for extra in ({"values_focus": ["family"]}, {"school_profile": {}}, {"context_mode": "universal"}):
            with self.subTest(extra=extra), self.assertRaises(RequestError):
                norm(minimal_request(**extra))

    def test_unknown_event(self):
        """Проверяет сценарий теста: unknown event."""
        with self.assertRaises(RequestError) as ctx:
            norm(minimal_request(event_id="sverdlovsk_region_day"))
        self.assertEqual(ctx.exception.code, "EVENT_NOT_FOUND")

    def test_t084_values_from_catalog(self):
        """Проверяет сценарий теста: t084 values from catalog."""
        n = norm(minimal_request(event_id="victory_day"))
        self.assertEqual(n.values, ["historical_memory", "citizenship"])
        self.assertTrue(n.educational_goals)

    def test_t107_api_mode_is_full(self):
        """Проверяет сценарий теста: t107 api mode is full."""
        n = norm(minimal_request())
        self.assertEqual((n.context_mode, n.cultural_context, n.experiment_tag), ("full", True, None))

    def test_control_chars_removed(self):
        """Проверяет сценарий теста: control chars removed."""
        n = norm(minimal_request(teacher_preferences={"notes": "текст\x07 с управляющим"}))
        self.assertEqual(n.teacher_preferences["notes"], "текст с управляющим")



class UniversalModeTest(unittest.TestCase):
    def test_universal_keeps_script_detail_only(self):
        """В universal предпочтения педагога сброшены к дефолтам, кроме подробности реплик."""
        raw = minimal_request(teacher_preferences={"style": "interactive", "script_detail": "detailed",
                                                   "interaction_level": "high", "group_work": True})
        n = norm(raw, context_mode="universal")
        self.assertEqual(n.teacher_preferences["script_detail"], "detailed")
        self.assertEqual(n.teacher_preferences["style"], "classic")
        self.assertEqual(n.teacher_preferences["interaction_level"], "low")
        self.assertIs(n.teacher_preferences["group_work"], False)
        self.assertEqual(n.effective_input["teacher_preferences"]["style"], "interactive")


if __name__ == "__main__":
    unittest.main()