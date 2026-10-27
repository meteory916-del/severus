"""Контракт 01: запрос фронтенда (заморожен, идентичен v1.4).

Модели повторяют правила ТЗ 6.2–6.4 и общего бэкенда `backend/schemas.py`.
Значения по умолчанию подставляются из `config/request_defaults.json`
функцией `apply_defaults()` ДО валидации, чтобы отсутствующее поле и явный
`null` различались (явный `null` у поля без null-типа - ошибка).
"""

from __future__ import annotations

import copy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

GradeGroup = Literal["1-4", "5-8", "9-11"]
EventFormat = Literal["class_hour", "school_event", "interactive_lesson"]
ParentRole = Literal["helper", "active_participant", "audience", "evaluator"]
AudienceEngagement = Literal["none", "feedback", "vote", "audience_award"]
RoomType = Literal["classroom", "assembly_hall", "gym", "other"]

def grade_to_group(grade: int) -> str:
    """Определяет возрастную группу 1-4, 5-8 или 9-11 по номеру класса.

    Параметры:
        `grade`.

    Возвращает:
        str.
    """
    if grade <= 4:
        return "1-4"
    if grade <= 8:
        return "5-8"
    return "9-11"


class Participants(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teachers_count: StrictInt = Field(ge=1)
    parents_enabled: StrictBool
    parents_count: StrictInt | None = Field(default=None, ge=0)
    parent_roles: list[ParentRole]
    parent_audience_engagement: AudienceEngagement
    parent_notes: str | None = None

    @model_validator(mode="after")
    def check_parents(self) -> "Participants":
        """Проверяет согласованность количества, ролей и режима участия родителей.

        Возвращает:
            'Participants'.
        """
        if not self.parents_enabled:
            if self.parents_count not in (None, 0):
                raise ValueError("Родители отключены, но указано их количество")
            if self.parent_roles:
                raise ValueError("Роли родителей заданы при отключённых родителях")
            if self.parent_audience_engagement != "none":
                raise ValueError("Зрительское вовлечение задано при отключённых родителях")
            self.parents_count = 0
        else:
            if self.parents_count is None or self.parents_count < 1:
                raise ValueError("При участии родителей нужно точное число родителей ≥ 1")
            if not self.parent_roles:
                self.parent_roles = ["audience"]
            if len(set(self.parent_roles)) != len(self.parent_roles):
                raise ValueError("Роли родителей не должны повторяться")
            if self.parent_audience_engagement != "none" and "audience" not in self.parent_roles:
                raise ValueError("Обратная связь, голосование и приз зрителей требуют роли audience")
        return self


class Resources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projector: StrictBool | None
    printer: StrictBool | None
    internet: StrictBool | None
    audio: StrictBool | None
    room: RoomType | None
    available_materials: list[str]
    extra_notes: str | None = None


class TeacherPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Literal["classic", "interactive", "creative", "research"]
    script_detail: Literal["brief", "standard", "detailed"]
    difficulty: Literal["basic", "standard", "advanced"]
    interaction_level: Literal["low", "medium", "high"]
    group_work: StrictBool
    preparation_effort: Literal["minimal", "standard", "extended"]
    notes: str | None = None


class GenerationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variants_count: StrictInt = Field(ge=1, le=3)
    language: Literal["ru"]


class GenerationRequest(BaseModel):
    """Эффективный (после дефолтов) запрос контракта 01."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    region_id: Literal["RU-SVE"]
    grade_group: GradeGroup | None = None
    grade: StrictInt | None = Field(default=None, ge=1, le=11)
    pupils_count: StrictInt = Field(ge=1, le=35)
    duration_minutes: Literal[30, 45, 60, 90]
    format: EventFormat
    participants: Participants
    resources: Resources
    teacher_preferences: TeacherPreferences
    generation: GenerationSettings

    @model_validator(mode="after")
    def check_grade(self) -> "GenerationRequest":
        """Проверяет соответствие точного класса возрастной группе и при необходимости вычисляет группу.

        Возвращает:
            'GenerationRequest'.
        """
        if self.grade is None and self.grade_group is None:
            raise ValueError("Укажите класс (grade) или возрастную группу (grade_group)")
        if self.grade is not None:
            expected = grade_to_group(self.grade)
            if self.grade_group is None:
                self.grade_group = expected
            elif self.grade_group != expected:
                raise ValueError("Класс не соответствует возрастной группе")
        return self


_NESTED = ("participants", "resources", "teacher_preferences", "generation")


def apply_defaults(raw: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Дополняет ОТСУТСТВУЮЩИЕ поля значениями по умолчанию (ТЗ 6.2.1).

    Явно переданные значения (включая некорректный null) не трогаются -
    их проверит валидатор. Условные правила для родителей применяются в
    модели `Participants`.
    """
    if not isinstance(raw, dict):
        raise TypeError("Запрос должен быть JSON-объектом")
    result = copy.deepcopy(raw)
    for key in _NESTED:
        base = copy.deepcopy(defaults.get(key, {}))
        given = result.get(key, None) if key in result else None
        if key not in result:
            result[key] = base
            continue
        if not isinstance(given, dict):
            continue  # пусть валидатор вернёт понятную ошибку
        merged = base
        merged.update(given)
        if key == "participants" and given.get("parents_enabled") is True:
            # при включённых родителях дефолт 0 не подставляем - число обязательно
            if "parents_count" not in given:
                merged["parents_count"] = None
            if "parent_roles" not in given:
                merged["parent_roles"] = ["audience"]
        result[key] = merged
    if "grade" not in result:
        result["grade"] = None
    return result