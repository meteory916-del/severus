"""Нужный объём реплик педагога в блоке: зависит от детализации и длительности блока."""

from __future__ import annotations

from typing import Any


def script_min_chars(gen_cfg: dict[str, Any], detail: str, minutes: int) -> int:
    """Минимальный объём `teacher_script` для блока.

    Объём = базовая часть (вступление, инструкция, переход) + часть на каждую минуту блока.
    Короткий переход на 2 минуты не обязан быть таким же длинным, как работа в командах на 20 минут.

    Параметры:
        gen_cfg: `config/generation.json`; detail: `brief` | `standard` | `detailed`; minutes: длительность блока.

    Возвращает:
        Число символов.
    """
    cfg = gen_cfg["script_length"]
    return int(cfg["base_chars"][detail] + cfg["chars_per_minute"][detail] * max(int(minutes), 1))


def script_target_chars(gen_cfg: dict[str, Any], detail: str, minutes: int) -> int:
    """Объём, к которому модель просим стремиться: в полтора раза больше минимума.

    Модели обычно пишут впритык к названному числу, поэтому в промпте называем и минимум, и желаемый объём,
    а предупреждение `SCRIPT-SHORT` даём только ниже минимума.
    """
    return int(round(script_min_chars(gen_cfg, detail, minutes) * 1.5, -1))


def script_size_text(gen_cfg: dict[str, Any], detail: str, minutes: int) -> str:
    """Например «от 600, лучше около 900 символов»."""
    return f"от {script_min_chars(gen_cfg, detail, minutes)}, лучше около {script_target_chars(gen_cfg, detail, minutes)} символов"


def script_length_rule(gen_cfg: dict[str, Any], detail: str) -> str:
    """Правило объёма словами с примерами для промпта: «5 мин - от 500, лучше около 750 символов; …»."""
    examples = "; ".join(f"{m} мин - {script_size_text(gen_cfg, detail, m)}" for m in (3, 5, 10, 20))
    return f"по длительности блока: {examples}"