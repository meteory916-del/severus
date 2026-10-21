"""Каталог событий, справочники ценностей и зависимостей, корпус источников, профиль школы."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .settings import Settings, read_json, sha256_file


@dataclass
class Catalog:
    events: dict[str, dict[str, Any]]
    values: dict[str, dict[str, Any]]
    dependencies: dict[str, dict[str, Any]]
    sources: dict[str, dict[str, Any]]
    fragments: dict[str, dict[str, Any]]
    school_profile: dict[str, Any]
    hashes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, settings: Settings) -> "Catalog":
        """Загружает каталог событий, справочники, корпус источников и профиль школы и проверяет их согласованность.

        Параметры:
            `settings`.

        Возвращает:
            'Catalog'.
        """
        root = settings.root / "catalog"
        hashes: dict[str, str] = {}
        events: dict[str, dict[str, Any]] = {}
        for path in sorted((root / "events").glob("*.json")):
            data = read_json(path)
            events[data["id"]] = data
            hashes[f"catalog/events/{path.name}"] = sha256_file(path)
        values_path = root / "values.json"
        deps_path = root / "dependencies.json"
        values = {v["value_id"]: v for v in read_json(values_path)["values"]}
        deps = {d["id"]: d for d in read_json(deps_path)["items"]}
        hashes["catalog/values.json"] = sha256_file(values_path)
        hashes["catalog/dependencies.json"] = sha256_file(deps_path)

        sources: dict[str, dict[str, Any]] = {}
        fragments: dict[str, dict[str, Any]] = {}
        for corpus in sorted((root / "regions").glob("*/verified_sources.json")):
            data = read_json(corpus)
            hashes[str(corpus.relative_to(settings.root)).replace("\\", "/")] = sha256_file(corpus)
            for src in data.get("sources", []):
                sources[src["source_id"]] = src
            for frag in data.get("fragments", []):
                fragments[frag["fragment_id"]] = frag

        profile_path = settings.school_profile_file
        profile = read_json(profile_path) if profile_path.is_file() else {}
        if profile_path.is_file():
            hashes["config/school_profile.json"] = sha256_file(profile_path)

        catalog = cls(events, values, deps, sources, fragments, profile, hashes)
        catalog.check_integrity()
        return catalog

    def check_integrity(self) -> None:
        """Проверяет внутреннюю согласованность каталога событий, ценностей и справочников.

        Возвращает:
            None.
        """
        for eid, event in self.events.items():
            if event.get("status", "active") != "active":
                continue
            if not event.get("values"):
                raise ValueError(f"У события {eid} не заданы ценности")
            if not event.get("educational_goals"):
                raise ValueError(f"У события {eid} не заданы воспитательные задачи")
            for value_id in event["values"]:
                if value_id not in self.values:
                    raise ValueError(f"У события {eid} неизвестная ценность {value_id}")

    def active_events(self) -> dict[str, dict[str, Any]]:
        """Возвращает только активные позиции каталога мероприятий.

        Возвращает:
            dict[str, dict[str, Any]].
        """
        return {k: v for k, v in self.events.items() if v.get("status", "active") == "active"}

    def verified_fragments(self, event_id: str, region_id: str, cultural_context: bool = True) -> list[dict[str, Any]]:
        """Проверенные фрагменты для события (ТЗ 17.2). Только status=verified."""
        event = self.events.get(event_id, {})
        topics = {t.split("/", 1)[-1] for t in event.get("regional_topics", [])}
        result = []
        for frag in self.fragments.values():
            if frag.get("verification_status", frag.get("status")) != "verified":
                continue
            if region_id not in frag.get("regions", [region_id]):
                continue
            by_event = event_id in frag.get("events", [])
            by_topic = bool(topics.intersection(frag.get("topics", [])))
            if by_topic and not cultural_context:
                continue
            if by_event or by_topic:
                result.append(frag)
        return result

    @staticmethod
    def profile_has_known_values(profile: dict[str, Any]) -> bool:
        """Проверяет, содержит ли профиль школы данные, которые нужно учитывать при персонализации.

        Параметры:
            `profile`.

        Возвращает:
            bool.
        """
        keys = ("settlement_type", "small_school", "local_context_notes")
        return any(profile.get(k) not in (None, "", False) for k in keys) or bool(profile.get("mixed_grade_classes"))


def path_or_none(path: Path) -> Path | None:
    """Возвращает путь, если он существует, иначе возвращает None.

    Параметры:
        `path`.

    Возвращает:
        Path | None.
    """
    return path if path.exists() else None