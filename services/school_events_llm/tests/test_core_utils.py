import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from app.generation.grouping import compute_grouping, describe, pairs, split_even
from app.generation.timing import TimingError, build_grid, check_grid, normalize_minutes
from app.llm.jsonx import JSONExtractionError, extract_json, strip_reasoning
from app.llm.mutex import MutexTimeout, _file_lock, local_llm_lock


def _lock_worker(path: str, enabled: bool, hold_seconds: float, wait_seconds: float, queue) -> None:
    """Выполняет внутреннюю служебную операцию `_lock_worker` в рамках текущего модуля.

    Параметры:
        `path`, `enabled`, `hold_seconds`, `wait_seconds`, `queue`.

    Возвращает:
        None.
    """
    try:
        with local_llm_lock(Path(path), wait_seconds, enabled=enabled) as info:
            queue.put({"status": "acquired", "kind": info["kind"], "wait_ms": info.get("wait_ms", 0)})
            time.sleep(hold_seconds)
    except MutexTimeout:
        queue.put({"status": "timeout"})



class TimingTest(unittest.TestCase):
    def test_exact_sum_kept(self):
        """Проверяет сценарий теста: exact sum kept."""
        self.assertEqual(normalize_minutes([5, 10, 20, 10], 45), [5, 10, 20, 10])

    def test_t008_scaled_to_exact_sum(self):
        """Проверяет сценарий теста: t008 scaled to exact sum."""
        for total in (30, 45, 60, 90):
            for proposed in ([5, 10, 20, 10], [3, 3, 3], [10, 40, 25, 5, 15], [1, 1, 50]):
                with self.subTest(total=total, proposed=proposed):
                    result = normalize_minutes(proposed, total)
                    self.assertEqual(sum(result), total)
                    self.assertTrue(all(m >= 2 for m in result))

    def test_too_many_blocks(self):
        """Проверяет сценарий теста: too many blocks."""
        with self.assertRaises(TimingError):
            normalize_minutes([1] * 16, 30)

    def test_grid(self):
        """Проверяет сценарий теста: grid."""
        grid = build_grid([5, 10, 30])
        self.assertEqual(grid, [(0, 5), (5, 10), (15, 30)])
        blocks = [{"block_id": f"b{i}", "start_minute": s, "duration_minutes": d} for i, (s, d) in enumerate(grid)]
        self.assertEqual(check_grid(blocks, 45), [])
        blocks[1]["start_minute"] = 6
        self.assertTrue(check_grid(blocks, 45))


class GroupingTest(unittest.TestCase):
    def test_t007_27_pupils(self):
        """Проверяет сценарий теста: t007 27 pupils."""
        self.assertEqual(split_even(27, 5), [6, 6, 5, 5, 5])
        self.assertEqual(describe([6, 6, 5, 5, 5]), "5 групп: 6, 6, 5, 5, 5")

    def test_pairs(self):
        """Проверяет сценарий теста: pairs."""
        self.assertEqual(sum(pairs(27)), 27)
        self.assertEqual(pairs(27).count(3), 1)
        self.assertEqual(describe(pairs(27)), "12 пар и одна тройка")

    def test_group_work_false_replaces_small_groups(self):
        """Проверяет сценарий теста: group work false replaces small groups."""
        mode, sizes, notes = compute_grouping("small_groups", 20, 4, group_work=False)
        self.assertEqual((mode, sizes), ("whole_class", [20]))
        self.assertTrue(notes)


class JsonExtractTest(unittest.TestCase):
    def test_reasoning_and_fence(self):
        """Проверяет сценарий теста: reasoning and fence."""
        text = '<think>рассуждаю {не json}</think>\nВот ответ:\n```json\n{"a": 1, "b": [1, 2,],}\n```'
        self.assertEqual(extract_json(text), {"a": 1, "b": [1, 2]})

    def test_unclosed_think_prefix(self):
        """Проверяет сценарий теста: unclosed think prefix."""
        cleaned, had = strip_reasoning("размышления без открывающего тега</think>{\"x\": 2}")
        self.assertTrue(had)
        self.assertEqual(extract_json(cleaned), {"x": 2})

    def test_braces_inside_strings(self):
        """Проверяет сценарий теста: braces inside strings."""
        self.assertEqual(extract_json('мусор {"t": "скобка } внутри"} хвост'), {"t": "скобка } внутри"})

    def test_invalid(self):
        """Проверяет сценарий теста: invalid."""
        with self.assertRaises(JSONExtractionError):
            extract_json('{"oops": ')


class FileLockTest(unittest.TestCase):
    def test_t022_second_holder_waits_and_times_out(self):
        """Проверяет сценарий теста: t022 second holder waits and times out."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lm.lock"
            with _file_lock(path, 1):
                started = time.monotonic()
                with self.assertRaises(MutexTimeout):
                    with _file_lock(path, 0.4):
                        pass
                self.assertGreaterEqual(time.monotonic() - started, 0.35)
            with _file_lock(path, 0.4) as info:
                self.assertEqual(info["kind"], "file")


    def test_t111_two_processes_share_file_lock_only_when_enabled(self):
        """Проверяет сценарий теста: t111 two processes share file lock only when enabled."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "shared.lock")
            ctx = multiprocessing.get_context("spawn")

            first_queue = ctx.Queue()
            first = ctx.Process(target=_lock_worker, args=(path, True, 2.0, 3.0, first_queue))
            first.start()
            self.assertEqual(first_queue.get(timeout=3)["status"], "acquired")

            second_queue = ctx.Queue()
            second = ctx.Process(target=_lock_worker, args=(path, True, 0.0, 0.3, second_queue))
            second.start()
            self.assertEqual(second_queue.get(timeout=3)["status"], "timeout")
            second.join(timeout=3)
            first.join(timeout=3)
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())

            free_queue_1 = ctx.Queue()
            free_queue_2 = ctx.Queue()
            free_1 = ctx.Process(target=_lock_worker, args=(path, False, 0.6, 1.0, free_queue_1))
            free_1.start()
            self.assertEqual(free_queue_1.get(timeout=3)["status"], "acquired")
            free_2 = ctx.Process(target=_lock_worker, args=(path, False, 0.0, 0.3, free_queue_2))
            free_2.start()
            self.assertEqual(free_queue_2.get(timeout=3)["status"], "acquired")
            free_2.join(timeout=3)
            free_1.join(timeout=3)
            self.assertFalse(free_1.is_alive())
            self.assertFalse(free_2.is_alive())

    def test_inter_process_lock_disabled_by_default(self):
        """Проверяет сценарий теста: inter process lock disabled by default."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lm.lock"
            with local_llm_lock(path, 1) as info:
                self.assertEqual(info["kind"], "queue_only")
            self.assertFalse(path.exists())
            with local_llm_lock(path, 1, enabled=True) as info:
                self.assertEqual(info["kind"], "file")
                with self.assertRaises(MutexTimeout):
                    with _file_lock(path, 0.3):
                        pass


if __name__ == "__main__":
    unittest.main()