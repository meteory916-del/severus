<!-- id: output.variation_plan | version: 1.0.0 -->
## Формат ответа

Верни один JSON-объект. В `concepts` ровно {{variants_count}} элемент(а), `variant_id` - {{variant_ids}}.

```json
{
  "schema_version": "1.2",
  "task": "variation_plan",
  "concepts": [
    {
      "variant_id": "v1",
      "title": "Короткое яркое название",
      "summary": "2–3 предложения: о чём событие и что делают участники",
      "narrative_approach": "Сюжетный ход: с чего начинается и к чему приводит",
      "primary_mechanic": "одно из: collaborative_planning | team_game | quest_route | mini_project | source_research | creative_workshop | performance | discussion_club | quiz_competition | interview_research",
      "engagement_mode": "одно из: whole_class | pairs | small_groups | mixed",
      "planned_structure": [
        {"order": 1, "title": "Название блока", "activity_type": "discussion", "approx_minutes": 5}
      ],
      "key_activities": [
        {"activity_type": "team_task", "description": "Что делают участники"}
      ],
      "distinctive_result": "Что конкретно останется после мероприятия",
      "differs_from": [
        {"variant_id": "v2", "difference": "Чем по сути отличается"}
      ],
      "values_to_mechanics": [
        {"value_id": "{{first_value_id}}", "mechanic_type": "одно из допустимых для ценности", "mechanic": "Как ценность реализуется действием участников"}
      ]
    }
  ]
}
```

`activity_type`: discussion | team_task | pair_task | individual_task | game | quiz | source_work | creative_product | performance | project_pitch | research | reflection | voting.
`mechanic_type`: family_research | team_task | source_work | joint_product | culture_comparison | real_problem_solving | class_collective_task | pair_task | discussion.
В `values_to_mechanics` - ровно ценности события: {{value_ids}}.