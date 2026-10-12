from __future__ import annotations

import csv
from pathlib import Path

base = Path(__file__).resolve().parents[1]
path = base / 'data' / 'questions.csv'
if not path.exists():
    print('Pending: build dataset before generating the evaluation split.')
    raise SystemExit(0)

rows = list(csv.DictReader(path.open('r', encoding='utf-8')))
selected = []
for category in ['technical', 'hr', 'behavioral']:
    cat_rows = [row for row in rows if row['category'] == category][:20]
    for row in cat_rows:
        selected.append({'id': row['id'], 'category': row['category'], 'question': row['question'], 'reference_answer': row['reference_answer'], 'human_rating': ''})

out = base / 'data' / 'eval_split.csv'
with out.open('w', newline='', encoding='utf-8') as fh:
    writer = csv.DictWriter(fh, fieldnames=['id', 'category', 'question', 'reference_answer', 'human_rating'])
    writer.writeheader()
    writer.writerows(selected)
print(f'Wrote {len(selected)} eval rows to {out}')
