<!-- id: output.scenario_blocks | version: 1.0.0 -->
## Формат ответа

Верни один JSON-объект со всеми блоками варианта `{{variant_id}}` в порядке плана. Время, ID, роли и материалы - как в плане.

```json
{
  "schema_version": "1.2",
  "task": "scenario_blocks",
  "variant_id": "{{variant_id}}",
  "blocks": [
    {
      "block_id": "block_01",
      "start_minute": 0,
      "duration_minutes": 5,
      "title": "Как в плане",
      "purpose": "Как в плане",
      "teacher_script": "Реплики педагога прямой речью и инструкции. Не меньше {{script_min_chars}} символов.",
      "pupil_actions": ["Конкретное действие учеников"],
      "role_ids": ["teacher_1", "pupils_all"],
      "material_ids": []
    }
  ],
  "fact_claims": []
}
```

Элемент `fact_claims`: `{"claim_id": "fc_01", "text": "утверждение", "location": "timeline.block_02.teacher_script", "source_id": "…", "fragment_id": "…", "needs_teacher_check": false}`.