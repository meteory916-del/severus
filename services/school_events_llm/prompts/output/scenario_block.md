<!-- id: output.scenario_block | version: 1.2.0 -->
## Формат ответа

Верни один JSON-объект для блока `{{block_id}}` варианта `{{variant_id}}`. Время, ID, роли и материалы - как в плане.

```json
{
  "schema_version": "1.2",
  "task": "scenario_block",
  "variant_id": "{{variant_id}}",
  "block": {
    "block_id": "{{block_id}}",
    "start_minute": {{start_minute}},
    "duration_minutes": {{block_minutes}},
    "title": "Как в плане",
    "purpose": "Как в плане",
    "teacher_script": "Полный текст для педагога: реплики в кавычках, действия в скобках. Объём {{script_min_chars}}.",
    "pupil_actions": ["Что делают ученики сначала (в каком составе)", "Что делают дальше и что получается"],
    "role_ids": ["teacher_1", "pupils_all"],
    "material_ids": []
  },
  "fact_claims": []
}
```