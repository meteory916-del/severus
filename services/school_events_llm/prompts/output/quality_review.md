<!-- id: output.quality_review | version: 1.0.0 -->
## Формат ответа

Верни один JSON-объект проверки варианта `{{variant_id}}`.

```json
{
  "schema_version": "1.2",
  "task": "quality_review",
  "variant_id": "{{variant_id}}",
  "findings": [
    {
      "rule_code": "VAL-003",
      "severity_suggested": "warning",
      "location": "timeline.block_02",
      "message": "Описание найденной проблемы",
      "suggested_action": "Конкретное предложение по исправлению"
    }
  ],
  "fact_claims_review": [
    {
      "claim_id": "fc_01",
      "matches_fragment": true,
      "comment": "Краткий комментарий"
    }
  ]
}
```

`severity_suggested`: `info`, `warning` или `critical`. Итоговую серьёзность и статус определяет backend.