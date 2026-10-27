import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.catalog import Catalog, CatalogError
from app.normalize import RequestError, normalize
from app.prompting.composer import Composer
from app.settings import Settings
from tests.helpers import ROOT, SHARED_CATALOG, catalog, minimal_request, settings

STAGES = ("variation_plan", "scenario_plan", "scenario_blocks", "scenario_block", "materials", "quality_review")
GRADE_FOR_GROUP = {"1-4": 3, "5-8": 6, "9-11": 10}


def temp_catalog(tmp: str) -> Path:
    """Копирует общий каталог во временную папку, чтобы тест мог его портить."""
    target = Path(tmp) / "catalog"
    shutil.copytree(SHARED_CATALOG / "events", target / "events")
    shutil.copytree(SHARED_CATALOG / "sources", target / "sources")
    return target


def edit_card(catalog_dir: Path, event_id: str, **changes) -> None:
    """Изменяет выбранные поля временной карточки события для негативного теста."""
    path = catalog_dir / "events" / f"{event_id}.json"
    card = json.loads(path.read_text(encoding="utf-8"))
    for key, value in changes.items():
        if value is None:
            card.pop(key, None)
        else:
            card[key] = value
    path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")


class SharedCatalogTest(unittest.TestCase):
    """Сервис читает общий каталог проекта и проверяет его при загрузке."""

    def test_service_accepts_every_catalog_event(self):
        """Генератор принимает ровно те события, что лежат в общем каталоге (их же бэкенд отдаёт фронтенду)."""
        on_disk = sorted(p.stem for p in (SHARED_CATALOG / "events").glob("*.json"))
        self.assertEqual(len(on_disk), 14)
        self.assertEqual(sorted(catalog().active_events()), on_disk)
        self.assertNotIn("ural_culture", on_disk)
        for event_id in ("sverdlovsk_oblast_day", "middle_urals_peoples_day"):
            with self.subTest(event_id=event_id):
                n = normalize(minimal_request(event_id=event_id), catalog(), settings())
                self.assertEqual(n.event_id, event_id)

    def test_unknown_event_is_rejected(self):
        """Событие, которого нет в каталоге, генератор отклоняет."""
        with self.assertRaises(RequestError) as ctx:
            normalize(minimal_request(event_id="ural_culture"), catalog(), settings())
        self.assertEqual(ctx.exception.code, "EVENT_NOT_FOUND")

    def test_every_supported_combination_composes(self):
        """Каждое событие каталога собирается во всех возрастах, форматах и этапах без пустых переменных."""
        all_active = catalog()
        composer = Composer(settings(), all_active)
        out_vars = {"variant_id": "v1", "block_id": "block_01", "start_minute": "0", "block_minutes": "5"}
        for event_id, event in sorted(all_active.events.items()):
            for group in event["supported_age_groups"]:
                for fmt in event["supported_formats"]:
                    raw = minimal_request(event_id=event_id, grade=GRADE_FOR_GROUP[group], grade_group=group, format=fmt)
                    n = normalize(raw, all_active, settings())
                    for stage in STAGES:
                        with self.subTest(event=event_id, group=group, fmt=fmt, stage=stage):
                            composed = composer.compose(stage, n, stage_input="", output_vars=out_vars)
                            text = "\n".join(m["content"] for m in composed.messages)
                            self.assertNotIn("{{", text)
                            ids = [m["id"] for m in composed.manifest]
                            self.assertIn(f"events.{event_id}", ids)
                            self.assertIn("events.card", ids)

    def test_problems_are_reported_together(self):
        """Ошибки карточек собираются в одно сообщение, а не останавливаются на первой."""
        with tempfile.TemporaryDirectory() as tmp:
            cat_dir = temp_catalog(tmp)
            edit_card(cat_dir, "knowledge_day", values=None)
            edit_card(cat_dir, "teachers_day", values=["friendship"])
            edit_card(cat_dir, "victory_day", age_appropriateness_notes={"1-4": "x", "5-8": "y"})
            edit_card(cat_dir, "new_year", category="calendar")
            with self.assertRaises(CatalogError) as ctx:
                Catalog.load(Settings(root=ROOT, env={"CATALOG_DIR": str(cat_dir)}))
            problems = "\n".join(ctx.exception.problems)
            self.assertIn("events/knowledge_day.json: нет поля values", problems)
            self.assertIn("events/teachers_day.json: неизвестная ценность 'friendship'", problems)
            self.assertIn("events/victory_day.json: нет возрастного совета для группы 9-11", problems)
            self.assertIn("events/new_year.json: category", problems)
            self.assertGreaterEqual(len(ctx.exception.problems), 4)

    def test_event_without_service_prompt_block_is_reported(self):
        """Новое событие в каталоге без блока prompts/events/<id>.md в сервисе - ошибка загрузки."""
        with tempfile.TemporaryDirectory() as tmp:
            cat_dir = temp_catalog(tmp)
            card = json.loads((cat_dir / "events" / "knowledge_day.json").read_text(encoding="utf-8"))
            card["id"] = "new_event"
            (cat_dir / "events" / "new_event.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(CatalogError) as ctx:
                Catalog.load(Settings(root=ROOT, env={"CATALOG_DIR": str(cat_dir)}))
            self.assertIn("events/new_event.json: в сервисе нет блока prompts/events/new_event.md", ctx.exception.problems)

    def test_missing_catalog_dir(self):
        """Если общий каталог не найден, сообщение подсказывает переменную CATALOG_DIR."""
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(CatalogError) as ctx:
            Catalog.load(Settings(root=ROOT, env={"CATALOG_DIR": str(Path(tmp) / "nope")}))
        self.assertIn("CATALOG_DIR", str(ctx.exception))

    def test_draft_fragments_do_not_reach_prompt(self):
        """Черновые фрагменты каталога не попадают в справочный блок промпта."""
        drafts = [f for f in catalog().fragments.values() if f.get("verification_status") == "draft"]
        self.assertTrue(drafts)
        self.assertEqual(catalog().verified_fragments("victory_day", "RU-SVE"), [])


if __name__ == "__main__":
    unittest.main()