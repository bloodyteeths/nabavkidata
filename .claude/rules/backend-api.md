---
paths: backend/api/**/*.py
---

# Backend API Development Rules

## Database Connections
- Always use `asyncpg` for async database operations
- Connection pool is managed in `backend/db.py`
- Use parameterized queries to prevent SQL injection

## JSONB Column Handling
When reading JSONB columns with asyncpg, they return as strings, not dicts:
```python
import json
if isinstance(jsonb_value, str):
    data = json.loads(jsonb_value) if jsonb_value else {}
elif isinstance(jsonb_value, dict):
    data = jsonb_value
else:
    data = {}
```

## Bilingual Search (Latin/Cyrillic)
Always support both Latin input and Macedonian Cyrillic in search:
```python
from backend.api.corruption import latin_to_cyrillic, build_bilingual_search_condition
```

## Error Handling
- Return proper HTTP status codes
- Log errors with context
- Return user-friendly error messages in Macedonian

## Performance
- Use materialized views for expensive aggregations
- Add indexes for frequently filtered columns
- Consider pagination for large result sets (default: 50 items)
