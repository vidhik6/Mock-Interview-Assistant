from __future__ import annotations

import csv
from pathlib import Path

base = Path(__file__).resolve().parents[1]
path = base / 'data' / 'eval_split.csv'
if not path.exists():
    print('Pending: human ratings are not available yet.')
    raise SystemExit(0)
rows = list(csv.DictReader(path.open('r', encoding='utf-8')))
print(f'Loaded {len(rows)} rows; ratings remain blank until human annotators complete the template.')
