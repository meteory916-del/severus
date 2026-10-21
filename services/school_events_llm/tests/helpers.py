import copy
import json
from pathlib import Path

from app.catalog import Catalog
from app.settings import SERVICE_ROOT, Settings

ROOT = SERVICE_ROOT
EXAMPLES = ROOT / "examples"
EXAMPLE_NAMES = ["ex1_knowledge_day", "ex2_mothers_day", "ex3_labour_day"]

_settings = None
_catalog = None


def settings() -> Settings:
    """Возвращает общий объект настроек тестового окружения.

    Возвращает:
        Settings.
    """
    global _settings
    if _settings is None:
        _settings = Settings(root=ROOT, env={})
    return _settings


def catalog() -> Catalog:
    """Возвращает загруженный каталог тестового окружения.

    Возвращает:
        Catalog.
    """
    global _catalog
    if _catalog is None:
        _catalog = Catalog.load(settings())
    return _catalog


def load_json(path: Path):
    """Загружает тестовый JSON-файл.

    Параметры:
        `path`.
    """
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def request(name: str) -> dict:
    """Загружает пример входного запроса по имени сценария.

    Параметры:
        `name`.

    Возвращает:
        dict.
    """
    return load_json(EXAMPLES / "requests" / f"{name}.json")


def golden(name: str) -> dict:
    """Загружает эталон внутренней генерации по имени сценария.

    Параметры:
        `name`.

    Возвращает:
        dict.
    """
    return load_json(EXAMPLES / "golden" / f"{name}.json")


def minimal_request(**overrides) -> dict:
    """Создаёт минимальный корректный запрос и применяет переданные переопределения.

    Параметры:
        `**overrides`.

    Возвращает:
        dict.
    """
    data = {"event_id": "knowledge_day", "region_id": "RU-SVE", "grade_group": "5-8", "pupils_count": 25,
            "duration_minutes": 45, "format": "class_hour"}
    data.update(overrides)
    return copy.deepcopy(data)


def contract02_variant_keys() -> set[str]:
    """Ключи варианта из примера замороженного контракта 02 (docs/tz)."""
    text = (ROOT / "docs" / "tz" / "02_BACKEND_RESPONSE_TO_FRONTEND_v1.5.md").read_text(encoding="utf-8")
    start = text.index("```json") + len("```json")
    end = text.index("```", start)
    example = json.loads(text[start:end])
    return set(example["variants"][0].keys())