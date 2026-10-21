import re
import unittest

from tests.helpers import EXAMPLES

# Частые детские имена (полные и уменьшительные) в основе; окончание покрывает падежи.
# Слово должно начинаться с заглавной буквы и быть отдельным словом, чтобы не ловить части других слов.
NAME_STEMS = (
    "Ан[яиеюй]", "Анн[аыеуой]", "Маш[аиеуой]", "Мари[яиеюй]", "Пет[яиеюй]", "Вас[яиеюй]", "Ван[яиеюй]",
    "Кат[яиеюй]", "Саш[аиеуой]", "Дим[аыеуой]", "Миш[аиеуой]", "Кол[яиеюй]", "Наст[яиеюй]", "Даш[аиеуой]",
    "Тан[яиеюй]", "Ол[яиеюй]", "Лен[аыеуой]", "Артём[аеуом]?", "Иван[аеуом]?", "Серёж[аиеуой]", "Алёш[аиеуой]",
    "Полин[аыеуой]", "Соф[ьи][яиеюй]", "Егор[аеуом]?", "Максим[аеуом]?",
)
NAME_PATTERN = re.compile(r"(?<![А-Яа-яЁё])(" + "|".join(NAME_STEMS) + r")(?![А-Яа-яЁё])")


class GoldenExamplesSafetyTest(unittest.TestCase):
    """Проверяет, что эталоны не нарушают базовые правила системного промпта."""

    def test_examples_do_not_invent_named_pupils(self):
        """В эталонах нет имён конкретных детей: только обезличенные формулировки.

        Проверка охватывает внутренние JSON, ответ по контракту 02 и читаемую Markdown-версию.
        """
        roots = [EXAMPLES / "golden", EXAMPLES / "rendered", EXAMPLES / "readable"]
        for root in roots:
            for path in sorted(root.glob("*")):
                if not path.is_file():
                    continue
                found = sorted(set(NAME_PATTERN.findall(path.read_text(encoding="utf-8"))))
                with self.subTest(file=f"{root.name}/{path.name}"):
                    self.assertEqual(found, [], f"Найдены имена: {found}")

    def test_name_pattern_catches_names_in_cases(self):
        """Шаблон ловит имена в разных падежах и не срабатывает на обычные слова."""
        self.assertTrue(NAME_PATTERN.search("«Аня уже предложила»"))
        self.assertTrue(NAME_PATTERN.search("слово Маше и Пете"))
        self.assertIsNone(NAME_PATTERN.search("Анализ задания, Олимпиада, Колонна, Данные"))


if __name__ == "__main__":
    unittest.main()