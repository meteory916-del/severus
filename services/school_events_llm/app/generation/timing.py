"""TimingService (ТЗ 11): точная сетка блоков считается кодом, а не моделью."""

from __future__ import annotations


class TimingError(ValueError):
    pass


def normalize_minutes(proposed: list[int], total: int, min_block: int = 2) -> list[int]:
    """Приводит предложенные минуты к точной сумме `total`.

    Пропорциональное масштабирование с округлением методом наибольших остатков;
    каждый блок не короче `min_block`. Порядок и относительный вес блоков сохраняются.
    """
    if not proposed:
        raise TimingError("Нет блоков для расчёта тайминга")
    n = len(proposed)
    if n * min_block > total:
        raise TimingError(f"{n} блоков не помещаются в {total} минут при минимуме {min_block} минуты на блок")
    weights = [max(1, int(p)) for p in proposed]
    if sum(weights) == total and all(w >= min_block for w in weights):
        return weights
    free = total - n * min_block
    extra = [max(0, w - min_block) for w in weights]
    extra_sum = sum(extra)
    if extra_sum == 0:
        shares = [free / n] * n
    else:
        shares = [free * e / extra_sum for e in extra]
    floors = [int(s) for s in shares]
    remainder = free - sum(floors)
    order = sorted(range(n), key=lambda i: (shares[i] - floors[i], weights[i]), reverse=True)
    for i in order[:remainder]:
        floors[i] += 1
    result = [min_block + f for f in floors]
    assert sum(result) == total
    return result


def build_grid(minutes: list[int]) -> list[tuple[int, int]]:
    """[(start_minute, duration)] - последовательно, без разрывов, с нуля."""
    grid, start = [], 0
    for m in minutes:
        grid.append((start, m))
        start += m
    return grid


def check_grid(blocks: list[dict], total: int) -> list[str]:
    """Проверяет непрерывность временной сетки и точное совпадение с общей длительностью.

    Параметры:
        `blocks`, `total`.

    Возвращает:
        list[str].
    """
    problems = []
    if not blocks:
        return ["Пустой тайминг"]
    if blocks[0]["start_minute"] != 0:
        problems.append("Первый блок должен начинаться с 0")
    expected = 0
    for b in blocks:
        if b["duration_minutes"] <= 0:
            problems.append(f"{b['block_id']}: длительность должна быть положительной")
        if b["start_minute"] != expected:
            problems.append(f"{b['block_id']}: начало {b['start_minute']}, ожидалось {expected}")
        expected = b["start_minute"] + b["duration_minutes"]
    if sum(b["duration_minutes"] for b in blocks) != total:
        problems.append(f"Сумма длительностей {sum(b['duration_minutes'] for b in blocks)} ≠ {total}")
    return problems