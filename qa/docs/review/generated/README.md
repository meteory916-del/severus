# Отрендеренные сценарии E2E (28.10.2026)

Читаемые версии всех 18 сценариев, полученных на живой модели. Это исходный текст генерации, без ручной правки.

| ID | Файл | Событие | `quality_report` |
|---|---|---|---|
| E2E-01 | [knowledge_day_6_45](E2E-01_knowledge_day_6_45.md) | День знаний, 6 класс | `passed` |
| E2E-02 | [knowledge_day_2_30](E2E-02_knowledge_day_2_30.md) | День знаний, 2 класс | `passed` |
| E2E-03 | [victory_day_10_90](E2E-03_victory_day_10_90.md) | День Победы, 10 класс | `passed` |
| E2E-04 | [mothers_day_45](E2E-04_mothers_day_45.md) | День матери | `warning`: `RESOURCE-UNKNOWN` |
| E2E-05 | [teachers_day_45](E2E-05_teachers_day_45.md) | День учителя | `passed` |
| E2E-06 | [knowledge_day_60_school](E2E-06_knowledge_day_60_school.md) | День знаний, общешкольное | `passed` |
| E2E-07 | [unity_day_60](E2E-07_unity_day_60.md) | День народного единства | `passed` |
| E2E-08 | [teachers_day_30_min](E2E-08_teachers_day_30_min.md) | День учителя, минимальные ресурсы | `passed` |
| E2E-09 | [new_year_45](E2E-09_new_year_45.md) | Новый год | `passed` |
| E2E-10 | [knowledge_day_8_30](E2E-10_knowledge_day_8_30.md) | День знаний, 8 учеников | `passed` |
| E2E-11 | [last_bell_11_45](E2E-11_last_bell_11_45.md) | Последний звонок, 11 класс | `passed` |
| E2E-12 | [womens_day_45](E2E-12_womens_day_45.md) | 8 Марта | `warning`: `PARENT-INSTRUCTION`, `RESOURCE-UNKNOWN` |
| E2E-13 | [christmas_45](E2E-13_christmas_45.md) | Рождество | `warning`: `FACT-UNREGISTERED` |
| E2E-14 | [defender_day_60](E2E-14_defender_day_60.md) | День защитника Отечества | `passed` |
| E2E-15 | [graduation_60](E2E-15_graduation_60.md) | Выпускной | `passed` |
| E2E-16 | [labour_day_60](E2E-16_labour_day_60.md) | Праздник Весны и Труда | `warning`: `FACT-UNREGISTERED` |
| E2E-17 | [middle_urals_45](E2E-17_middle_urals_45.md) | День народов Среднего Урала | `passed` |
| E2E-18 | [sverdlovsk_oblast_30](E2E-18_sverdlovsk_oblast_30.md) | День Свердловской области | `passed` |

## Как читать

1. Сверить сумму времени с запросом.
2. Проверить, хватает ли времени внутри блоков.
3. Сверить число учеников, групп, педагогов и родителей.
4. Проверить материалы и необходимость печати.
5. Оценить возраст, лексику и сложность.
6. Проверить факты, даты, регион.
7. Прочитать замечания в конце файла.

Полный чек-лист — `qa/docs/acceptance/CONTENT_REVIEW_CHECKLIST.md`. Как устроены артефакты — `qa/docs/testing/ARTIFACTS.md`.

## Как пересобрать

```bash
python qa/tools/render_runs.py
```

Скрипт использует `data/runs/<job_id>` LLM-сервиса. Эти данные локальные и в git не попадают.
