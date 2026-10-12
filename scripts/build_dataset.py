from __future__ import annotations

from pathlib import Path

from src.data.loaders import build_question_dataset

base = Path(__file__).resolve().parents[1]
rows = build_question_dataset(base / 'data' / 'questions.csv')
print(f'Built {len(rows)} rows')
by_category = {}
for row in rows:
    by_category[row['category']] = by_category.get(row['category'], 0) + 1
print('Counts by category:', by_category)
