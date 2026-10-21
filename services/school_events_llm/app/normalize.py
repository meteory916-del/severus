"""Нормализация запроса контракта 01 во внутренний объект (ТЗ 6.3–6.4).

Модель LLM дефолты не подставляет: всё вычисляется здесь, до сборки промпта.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import ValidationError

from .catalog import Catalog
from .contracts.request import GenerationRequest, apply_defaults
from .settings import sha256_file, Settings

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class RequestError(Exception):
    """Формально неверный запрос → HTTP 422 в API."""

    def __init__(self, code: str, message: str, field: str | None = None):
        """Создаёт стабильную ошибку входного запроса с кодом, полем и признаком возможности повтора.

        Параметры:
            `code`, `message`, `field`.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, Any]:
        """Преобразует объект в обычный словарь для сериализации и журналирования.

        Возвращает:
            dict[str, Any].
        """
        return {"error": {"code": self.code, "message": self.message, "field": self.field, "retryable": False}}


@dataclass
class Warning_:
    code: str
    message: str
    field: str | None = None


def size_group(pupils: int) -> str:
    """Определяет категорию численности школьников по точному количеству.

    Параметры:
        `pupils`.

    Возвращает:
        str.
    """
    if pupils <= 15:
        return "up_to_15"
    if pupils <= 25:
        return "from_16_to_25"
    return "from_26_to_35"


def parent_size_group(parents: int) -> str:
    """Определяет категорию численности родителей по точному количеству.

    Параметры:
        `parents`.

    Возвращает:
        str.
    """
    if parents <= 0:
        return "none"
    if parents <= 2:
        return "1-2"
    if parents <= 5:
        return "3-5"
    if parents <= 10:
        return "6-10"
    return "11_plus"


@dataclass
class NormalizedRequest:
    event_id: str
    event_title: str
    event_category: str
    region_id: str
    age_group: str
    grade: int | None
    pupils_count: int
    size_group: str
    duration_minutes: int
    format: str
    teachers_count: int
    parents_enabled: bool
    parents_count: int
    parent_size_group: str
    parent_roles: list[str]
    parent_audience_engagement: str
    parent_notes: str | None
    resources: dict[str, Any]
    available_resources: list[str]
    unavailable_resources: list[str]
    unknown_resources: list[str]
    teacher_preferences: dict[str, Any]
    variants_count: int
    language: str
    values: list[str]
    educational_goals: list[str]
    school_profile: dict[str, Any]
    context_mode: str = "full"
    cultural_context: bool = True
    experiment_tag: str | None = None
    experiment_pair_id: str | None = None
    warnings: list[Warning_] = field(default_factory=list)
    effective_input: dict[str, Any] = field(default_factory=dict)
    defaults_hash: str | None = None

    @property
    def group_work(self) -> bool:
        """Возвращает фактически применённый флаг групповой работы из предпочтений педагога.

        Возвращает:
            bool.
        """
        return bool(self.teacher_preferences["group_work"])

    def to_dict(self) -> dict[str, Any]:
        """Преобразует объект в обычный словарь для сериализации и журналирования.

        Возвращает:
            dict[str, Any].
        """
        data = asdict(self)
        data["warnings"] = [asdict(w) for w in self.warnings]
        return data


def _clean(text: str | None) -> str | None:
    """Удаляет управляющие символы из свободного пользовательского текста перед использованием в prompt.

    Параметры:
        `text`.

    Возвращает:
        str | None.
    """
    if text is None:
        return None
    return _CONTROL.sub("", text).strip() or None


def _first_error(exc: ValidationError) -> RequestError:
    """Преобразует первую ошибку Pydantic в стабильную ошибку входного контракта.

    Параметры:
        `exc`.

    Возвращает:
        RequestError.
    """
    err = exc.errors()[0]
    loc = [str(p) for p in err.get("loc", []) if not isinstance(p, int) or True]
    field_path = ".".join(loc) or None
    msg = err.get("msg", "Некорректное значение")
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, "):]
    code = "VALIDATION_ERROR"
    if field_path == "generation.variants_count":
        code = "INVALID_VARIANTS_COUNT"
        msg = "Количество вариантов должно быть от 1 до 3"
    elif field_path == "region_id":
        code = "UNSUPPORTED_REGION"
    return RequestError(code, msg, field_path)


def normalize(
    raw: dict[str, Any],
    catalog: Catalog,
    settings: Settings,
    *,
    context_mode: str = "full",
    cultural_context: bool = True,
    experiment_tag: str | None = None,
    experiment_pair_id: str | None = None,
) -> NormalizedRequest:
    """Проверяет контракт 01, применяет серверные дефолты и строит внутренний нормализованный контекст генерации.

    Параметры:
        `raw`, `catalog`, `settings`, `context_mode`, `cultural_context`, `experiment_tag`, `experiment_pair_id`.

    Возвращает:
        NormalizedRequest.
    """
    defaults = settings.request_defaults()
    try:
        effective = apply_defaults(raw, defaults)
        req = GenerationRequest.model_validate(effective)
    except TypeError as exc:
        raise RequestError("VALIDATION_ERROR", str(exc)) from exc
    except ValidationError as exc:
        raise _first_error(exc) from exc

    event = catalog.active_events().get(req.event_id)
    if event is None:
        raise RequestError("EVENT_NOT_FOUND", "Неизвестное мероприятие", "event_id")
    if req.grade_group not in event.get("supported_age_groups", []):
        raise RequestError("CONFLICTING_CONSTRAINTS", "Возрастная группа не поддерживается для этого события", "grade_group")
    if req.format not in event.get("supported_formats", []):
        raise RequestError("CONFLICTING_CONSTRAINTS", "Формат не поддерживается для этого события", "format")
    mode_cfg = settings.experiment_modes().get("modes", {}).get(context_mode)
    if mode_cfg is None:
        raise RequestError("VALIDATION_ERROR", "Неизвестный внутренний context_mode")
    if not cultural_context and event.get("category") in ("regional", "cultural"):
        raise RequestError("CONFLICTING_CONSTRAINTS", "Событие культурной/региональной категории нельзя генерировать без культурного контекста")

    p = req.participants
    raw_resources = req.resources.model_dump(mode="json")
    raw_resources["extra_notes"] = _clean(req.resources.extra_notes)
    raw_teacher_preferences = req.teacher_preferences.model_dump(mode="json")
    raw_teacher_preferences["notes"] = _clean(req.teacher_preferences.notes)
    internal_resources = (
        raw_resources
        if mode_cfg.get("resources_mode") == "actual"
        else dict(defaults.get("resources", {}))
    )
    if mode_cfg.get("include_teacher"):
        internal_teacher_preferences = raw_teacher_preferences
    else:
        # Без персонализации берутся дефолты, но поля из keep_teacher_fields сохраняются:
        # например, script_detail, чтобы универсальная версия не была короче по полноте (ТЗ 8.12).
        internal_teacher_preferences = dict(defaults.get("teacher_preferences", {}))
        for field_name in mode_cfg.get("keep_teacher_fields", []):
            internal_teacher_preferences[field_name] = raw_teacher_preferences[field_name]
    flags = ("projector", "printer", "internet", "audio")
    available = [name for name in flags if internal_resources.get(name) is True]
    unavailable = [name for name in flags if internal_resources.get(name) is False]
    unknown = [name for name in flags if internal_resources.get(name) is None]

    warnings: list[Warning_] = []
    gen_cfg = settings.generation()
    min_voters = int(gen_cfg.get("audience_award_min_voters_warning", 6))
    if p.parents_enabled and p.parent_audience_engagement in ("vote", "audience_award"):
        voters_max = p.parents_count
        if voters_max < min_voters:
            warnings.append(Warning_(
                "LOW_AUDIENCE_FOR_VOTING",
                f"Зрителей не больше {voters_max}: голосование малорепрезентативно. Режим сохранён; генератор предложит бережную форму подведения итогов.",
                "participants.parent_audience_engagement",
            ))
    if internal_teacher_preferences.get("preparation_effort") == "minimal" and req.format == "school_event" and req.duration_minutes == 90:
        warnings.append(Warning_("PREPARATION_CONFLICT", "Общешкольное мероприятие на 90 минут при минимальной подготовке: сценарий будет компактным.", "teacher_preferences.preparation_effort"))

    profile = dict(catalog.school_profile or {})
    if mode_cfg.get("include_school") and profile.get("typical_teachers_available") and profile["typical_teachers_available"] != p.teachers_count:
        warnings.append(Warning_("PROFILE_MISMATCH", "Число педагогов в запросе отличается от профиля школы; используется значение запроса.", "participants.teachers_count"))

    effective_input = req.model_dump(mode="json")
    effective_input["participants"]["parent_notes"] = _clean(p.parent_notes)
    effective_input["resources"]["extra_notes"] = _clean(req.resources.extra_notes)
    effective_input["teacher_preferences"]["notes"] = _clean(req.teacher_preferences.notes)

    return NormalizedRequest(
        event_id=req.event_id,
        event_title=event["title"],
        event_category=event.get("category", ""),
        region_id=req.region_id,
        age_group=req.grade_group,
        grade=req.grade,
        pupils_count=req.pupils_count,
        size_group=size_group(req.pupils_count),
        duration_minutes=req.duration_minutes,
        format=req.format,
        teachers_count=p.teachers_count,
        parents_enabled=p.parents_enabled,
        parents_count=p.parents_count or 0,
        parent_size_group=parent_size_group(p.parents_count or 0),
        parent_roles=list(p.parent_roles),
        parent_audience_engagement=p.parent_audience_engagement,
        parent_notes=_clean(p.parent_notes),
        resources=internal_resources,
        available_resources=available,
        unavailable_resources=unavailable,
        unknown_resources=unknown,
        teacher_preferences=internal_teacher_preferences,
        variants_count=req.generation.variants_count,
        language=req.generation.language,
        values=list(event["values"]),
        educational_goals=list(event["educational_goals"]),
        school_profile=profile,
        context_mode=context_mode,
        cultural_context=cultural_context,
        experiment_tag=experiment_tag,
        experiment_pair_id=experiment_pair_id,
        warnings=warnings,
        effective_input=effective_input,
        defaults_hash=sha256_file(settings.defaults_file),
    )