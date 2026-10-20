# Критерии качества — Итерация 1

## Реализованные проверки

### Critical (блокируют выдачу)
| Код | Проверка |
|-----|----------|
| MISSING_FIELD | `timeline`, `roles`, `materials` отсутствуют или не являются списками |
| MISSING_FIELD | `role_id` из `timeline.role_ids` не найден в `roles` |
| MISSING_FIELD | `material_id` из `timeline.material_ids` не найден в `materials` |
| MISSING_FIELD | `block_id` из `parent_participation_plan.block_ids` не найден в `timeline` |
| MISSING_FIELD | `participant_type='parent'` при `parents_enabled=false` |
| MISSING_FIELD | `parent_participation_plan.enabled=true` при `parents_enabled=false` |
| MISSING_FIELD | суммарный `count` родительских ролей в блоке превышает `parents_count` |

### High (требуют исправления)
| Код | Проверка |
|-----|----------|
| MISSING_FIELD | `concept.summary` отсутствует или пуст |
| MISSING_FIELD | `concept.goal` отсутствует или пуст |
| MISSING_FIELD | `teacher_instructions` отсутствует или пуст |
| MISSING_FIELD | `teacher_script` пуст в любом блоке `timeline` |
| TOO_FEW_BLOCKS | в `timeline` менее 2 блоков |
| MISSING_FIELD | `parent_participation_plan` отсутствует или `enabled=false` при `parents_enabled=true` |
| MISSING_FIELD | `printer_required=true`, но `printer` отсутствует в `materials` |

### Medium (эвристики)
| Код | Проверка |
|-----|----------|
| AGE_HEURISTIC | для группы `1-4`: блок длиннее 15 минут |

### Low (минорные замечания)
| Код | Проверка |
|-----|----------|
| AGE_HEURISTIC | для группы `1-4`: слова длиннее 12 букв в `teacher_script` |
| AGE_HEURISTIC | для группы `9-11`: все блоки ≤ 5 минут |

## Что пока не реализовано
- Культурный контент (соответствие региону, праздникам, тематике)
- LLM-as-judge для семантической оценки качества
- Глубокая возрастная оценка (когнитивная нагрузка, сложность языка)
- Валидация JSON Schema
- Проверка соответствия `pupils_count` и количества ролей

## Как запускать тесты
```bash
python -m pytest tests/unit/ -v
```

## Пример вызова в пайплайне
```python
from app.validation import validate_structure, validate_timing, check_age_heuristics

issues = []
issues += validate_structure(variant, input_data)
issues += validate_timing(variant, input_data)
issues += check_age_heuristics(variant, input_data)
criticals = [i for i in issues if i["severity"] == "critical"]
```

## Тестовые запросы
См. `tests/fixtures/inputs/` — 12 кейсов, покрывающих основные комбинации параметров.
