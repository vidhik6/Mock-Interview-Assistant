from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd
from bs4 import BeautifulSoup

DEFAULT_COLUMNS = ['id', 'category', 'subcategory', 'question', 'reference_answer', 'source', 'difficulty']


def html_to_text(value: str) -> str:
    if value is None:
        return ''
    text = BeautifulSoup(str(value), 'html.parser').get_text(' ', strip=True)
    return re.sub(r'\s+', ' ', text).strip()


def normalize_question(row: Dict[str, Any]) -> Dict[str, Any]:
    category = str(row.get('category', '')).strip().lower()
    if category not in {'technical', 'hr', 'behavioral'}:
        category = 'technical'
    return {
        'id': str(row.get('id') or row.get('question') or 'q').strip()[:80],
        'category': category,
        'subcategory': str(row.get('subcategory') or 'general').strip(),
        'question': html_to_text(row.get('question') or ''),
        'reference_answer': html_to_text(row.get('reference_answer') or ''),
        'source': str(row.get('source') or 'synthetic'),
        'difficulty': str(row.get('difficulty') or 'medium'),
    }


def dedupe_questions(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    cleaned = []
    for row in rows:
        q = (row.get('question') or '').strip().lower()
        if not q:
            continue
        key = q[:80]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(row)
    return cleaned


def load_supplemental_questions(path: Path) -> List[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8') as fh:
        items = json.load(fh)
    rows = [normalize_question(item) for item in items]
    return dedupe_questions(rows)


def load_seed_questions(path: Path) -> List[Dict[str, Any]]:
    return load_supplemental_questions(path)


def load_kaggle_questions(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    df = pd.read_csv(path)
    rows = []
    for _, row in df.iterrows():
        q = row.to_dict()
        q['source'] = 'kaggle'
        rows.append(normalize_question(q))
    return dedupe_questions(rows)


def load_hf_questions() -> List[Dict[str, Any]]:
    try:
        from datasets import load_dataset

        ds = load_dataset('ali-alkhars/interviews', split='train[:20]')
        rows = []
        for entry in ds:
            rows.append(normalize_question({
                'id': entry.get('id', len(rows)),
                'category': entry.get('category', 'technical'),
                'subcategory': entry.get('subcategory', 'general'),
                'question': entry.get('question'),
                'reference_answer': entry.get('reference_answer') or entry.get('answer'),
                'source': 'huggingface',
                'difficulty': entry.get('difficulty', 'medium'),
            }))
        return dedupe_questions(rows)
    except Exception as exc:  # pragma: no cover - dataset/network optional
        print(f'HF source unavailable: {exc}')
        return []


def load_questions(csv_path: Path | str) -> List[Dict[str, Any]]:
    csv_path = Path(csv_path)
    data_dir = Path(__file__).resolve().parents[2] / 'data'
    fallback_rows = dedupe_questions(
        load_supplemental_questions(data_dir / 'supplemental_hr_behavioral.json')
        + load_seed_questions(data_dir / 'seed_questions.json')
    )
    if not csv_path.exists():
        return fallback_rows
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return fallback_rows
    rows = []
    for _, row in df.iterrows():
        rows.append(normalize_question(row.to_dict()))
    rows = [row for row in rows if row.get('question') and row.get('reference_answer')]
    if not rows:
        return fallback_rows
    return dedupe_questions(rows)


def build_question_dataset(output_path: Path | str = None) -> List[Dict[str, Any]]:
    base = Path(__file__).resolve().parents[2]
    supplemental = load_supplemental_questions(base / 'data' / 'supplemental_hr_behavioral.json')
    seed = load_seed_questions(base / 'data' / 'seed_questions.json')
    kaggle = load_kaggle_questions(base / 'data' / 'kaggle_software_engineering_questions.csv')
    hf = load_hf_questions()
    merged = supplemental + seed + kaggle + hf
    cleaned = []
    seen = set()
    for row in merged:
        if not row.get('question') or not row.get('reference_answer'):
            continue
        key = (row.get('category', 'technical'), (row.get('question') or '')[:80].lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(row)
    if not cleaned:
        cleaned = supplemental[:50]
    output = Path(output_path) if output_path else base / 'data' / 'questions.csv'
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cleaned, columns=DEFAULT_COLUMNS).to_csv(output, index=False)
    return cleaned
