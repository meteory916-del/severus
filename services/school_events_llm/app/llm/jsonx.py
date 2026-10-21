"""Извлечение JSON из ответа модели: вырезка рассуждений, Markdown-обёрток и мусора."""

from __future__ import annotations

import json
import re
from typing import Any

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_THINK_OPEN = re.compile(r"^.*?</think>", re.S | re.I)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class JSONExtractionError(ValueError):
    pass


def strip_reasoning(text: str) -> tuple[str, bool]:
    """Удаляет блоки <think>…</think> (в т. ч. незакрытое начало). Возвращает (текст, был_ли_блок)."""
    had = bool(_THINK.search(text)) or "</think>" in text.lower()
    text = _THINK.sub("", text)
    if "</think>" in text.lower():
        text = _THINK_OPEN.sub("", text)
    return text.strip(), had


def _balanced_object(text: str) -> str | None:
    """Находит первый сбалансированный JSON-объект в произвольном тексте с учётом строк и экранирования.

    Параметры:
        `text`.

    Возвращает:
        str | None.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        start = text.find("{", start + 1)
    return None


def extract_json(text: str) -> dict[str, Any]:
    """Извлекает первый корректный JSON-объект из сырого текстового ответа модели.

    Параметры:
        `text`.

    Возвращает:
        dict[str, Any].
    """
    cleaned, _ = strip_reasoning(text)
    candidates = [cleaned]
    candidates += [m.group(1).strip() for m in _FENCE.finditer(cleaned)]
    obj = _balanced_object(cleaned)
    if obj:
        candidates.append(obj)
    last_error: Exception | None = None
    for cand in candidates:
        try:
            value = json.loads(cand)
        except json.JSONDecodeError as exc:
            last_error = exc
            # частая ошибка локальных моделей - запятая перед закрывающей скобкой
            fixed = re.sub(r",\s*([}\]])", r"\1", cand)
            try:
                value = json.loads(fixed)
            except json.JSONDecodeError:
                continue
        if isinstance(value, dict):
            return value
    raise JSONExtractionError(f"В ответе модели не найден корректный JSON-объект ({last_error})")