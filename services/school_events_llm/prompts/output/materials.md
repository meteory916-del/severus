<!-- id: output.materials | version: 1.2.0 -->
## Формат ответа

Верни один JSON-объект с материалами варианта `{{variant_id}}`.

```json
{
  "schema_version": "1.2",
  "task": "materials",
  "variant_id": "{{variant_id}}",
  "materials": [
    {
      "material_id": "как в плане",
      "type": "как в плане",
      "title": "Название",
      "used_in_blocks": ["block_03"],
      "audience": "teacher | pupil | pupils_group | parent | all",
      "content": "Полный готовый текст материала",
      "teacher_notes": "Как использовать",
      "print_required": false,
      "dependencies": ["paper"],
      "estimated_preparation_minutes": 5,
      "family_task": false
    }
  ],
  "teacher_instructions": ["Что подготовить заранее", "Как организовать класс", "Что делать, если что-то пошло не так"],
  "voting": {{voting_example}},
  "teacher_fallback": {{fallback_example}},
  "fact_claims": []
}
```

Материалы из плана: {{planned_materials_list}}. `material_id` каждого материала - ровно ID из этого списка, без изменений и без суффиксов вроде `_01`; `type` - как в списке.

Допустимые `dependencies`: {{dependency_ids}}. Это расходники и оборудование, а не материалы: в `material_id` их не используй.