"""Проверка кураторского корпуса культурно-исторических источников.

Команда не обращается в интернет. Она проверяет файлы источников общего каталога
`catalog/sources/<event_id>.json` (поля `sources` и `fragments`): структуру, уникальность
идентификаторов, статусы и покрытие каталога проверенными фрагментами.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .settings import Settings, read_json


@dataclass
class SourceCheckIssue:
    """Описывает одну найденную проблему корпуса источников."""

    code: str
    severity: str
    file: str
    location: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Возвращает проблему в сериализуемом виде для CLI и тестов."""
        return {
            "code": self.code,
            "severity": self.severity,
            "file": self.file,
            "location": self.location,
            "message": self.message,
        }


def _known_topics(events: dict[str, dict[str, Any]]) -> set[str]:
    """Собирает допустимые региональные темы из активного каталога событий."""
    result: set[str] = set()
    for event in events.values():
        for topic in event.get("regional_topics", []):
            result.add(topic)
            result.add(topic.split("/", 1)[-1])
    return result


def check_sources(settings: Settings) -> dict[str, Any]:
    """Проверяет все файлы ``catalog/sources/*.json`` и рассчитывает покрытие каталога.

    Параметры:
        settings: Настройки сервиса с корнем проекта.

    Возвращает:
        Словарь с итоговым статусом, списком ошибок и предупреждений, количеством
        источников и фрагментов, а также покрытием по событиям и региону.

    Проверки:
        - уникальность source_id и fragment_id;
        - непустой текст фрагмента;
        - допустимый статус;
        - наличие collected_by и verified_by у verified-фрагмента;
        - разные составитель и проверяющий;
        - ссылки только на существующие события и известные темы;
        - у каждого фрагмента указан source_id из списка источников корпуса.
    """
    catalog_dir = settings.catalog_dir
    events: dict[str, dict[str, Any]] = {}
    for path in sorted((catalog_dir / "events").glob("*.json")):
        event = read_json(path)
        events[event["id"]] = event
    known_topics = _known_topics(events)

    issues: list[SourceCheckIssue] = []
    source_ids: list[str] = []
    fragment_ids: list[str] = []
    fragment_sources: list[tuple[str, str, Any]] = []
    verified_by_event: Counter[str] = Counter()
    verified_by_region: Counter[str] = Counter()
    total_sources = 0
    total_fragments = 0
    verified_fragments = 0
    allowed_statuses = {"draft", "pending", "verified", "rejected", "expired"}

    corpora = sorted((catalog_dir / "sources").glob("*.json"))
    for corpus in corpora:
        rel = "catalog/sources/" + corpus.name
        data = read_json(corpus)
        sources = data.get("sources", [])
        fragments = data.get("fragments", [])
        total_sources += len(sources)
        total_fragments += len(fragments)

        for index, source in enumerate(sources):
            source_id = source.get("source_id")
            if not source_id:
                issues.append(SourceCheckIssue("SOURCE-ID-MISSING", "error", rel, f"sources[{index}]", "Не указан source_id"))
            else:
                source_ids.append(source_id)

        for index, fragment in enumerate(fragments):
            location = f"fragments[{index}]"
            fragment_id = fragment.get("fragment_id")
            if not fragment_id:
                issues.append(SourceCheckIssue("FRAGMENT-ID-MISSING", "error", rel, location, "Не указан fragment_id"))
            else:
                fragment_ids.append(fragment_id)
            fragment_sources.append((rel, location, fragment.get("source_id")))

            quote = fragment.get("quote") or fragment.get("text_excerpt")
            if not isinstance(quote, str) or not quote.strip():
                issues.append(SourceCheckIssue("FRAGMENT-EMPTY", "error", rel, location, "Пустой текст фрагмента"))

            status = fragment.get("verification_status", fragment.get("status", "draft"))
            if status not in allowed_statuses:
                issues.append(SourceCheckIssue("FRAGMENT-STATUS", "error", rel, location, f"Неизвестный статус: {status}"))

            for event_id in fragment.get("events", []):
                if event_id not in events:
                    issues.append(SourceCheckIssue("FRAGMENT-EVENT", "error", rel, location, f"Неизвестное событие: {event_id}"))
            for topic in fragment.get("topics", []):
                if topic not in known_topics:
                    issues.append(SourceCheckIssue("FRAGMENT-TOPIC", "error", rel, location, f"Неизвестная региональная тема: {topic}"))

            if status == "verified":
                verified_fragments += 1
                collected_by = fragment.get("collected_by")
                verified_by = fragment.get("verified_by")
                if not collected_by:
                    issues.append(SourceCheckIssue("FRAGMENT-COLLECTOR", "error", rel, location, "У verified-фрагмента нет collected_by"))
                if not verified_by:
                    issues.append(SourceCheckIssue("FRAGMENT-VERIFIER", "error", rel, location, "У verified-фрагмента нет verified_by"))
                if collected_by and verified_by and collected_by == verified_by:
                    issues.append(SourceCheckIssue("FRAGMENT-SEPARATION", "error", rel, location, "Составитель и проверяющий должны быть разными людьми"))
                for event_id in fragment.get("events", []):
                    if event_id in events:
                        verified_by_event[event_id] += 1
                for region_id in fragment.get("regions", []):
                    verified_by_region[region_id] += 1

    known_source_ids = set(source_ids)
    for rel, location, source_id in fragment_sources:
        if not source_id:
            issues.append(SourceCheckIssue("FRAGMENT-SOURCE-MISSING", "error", rel, location, "У фрагмента не указан source_id"))
        elif source_id not in known_source_ids:
            issues.append(SourceCheckIssue("FRAGMENT-SOURCE-UNKNOWN", "error", rel, location, f"source_id {source_id} нет в списке источников корпуса"))

    for duplicated in sorted(key for key, count in Counter(source_ids).items() if count > 1):
        issues.append(SourceCheckIssue("SOURCE-DUPLICATE", "error", "*", "sources", f"Повторяется source_id: {duplicated}"))
    for duplicated in sorted(key for key, count in Counter(fragment_ids).items() if count > 1):
        issues.append(SourceCheckIssue("FRAGMENT-DUPLICATE", "error", "*", "fragments", f"Повторяется fragment_id: {duplicated}"))

    historical_events = {"victory_day", "defender_day", "unity_day", "christmas"}
    coverage_events: dict[str, dict[str, int | bool]] = {}
    for event_id, event in sorted(events.items()):
        required = 3 if event_id in historical_events or event.get("category") in {"regional", "cultural"} else 1
        actual = verified_by_event[event_id]
        coverage_events[event_id] = {"required": required, "actual": actual, "covered": actual >= required}

    region_actual = verified_by_region["RU-SVE"]
    coverage = {
        "events": coverage_events,
        "region_RU_SVE": {"required": 15, "actual": region_actual, "covered": region_actual >= 15},
        "recommended_total": {"min": 60, "max": 80, "actual": verified_fragments},
    }
    errors = [issue for issue in issues if issue.severity == "error"]
    return {
        "status": "error" if errors else "ok",
        "sources_total": total_sources,
        "fragments_total": total_fragments,
        "verified_fragments": verified_fragments,
        "issues": [issue.to_dict() for issue in issues],
        "coverage": coverage,
    }