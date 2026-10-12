from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from src.scoring.config import CATEGORY_LENGTH_TARGETS, COMPLETENESS_THRESHOLD, OVERALL_WEIGHTS
from src.scoring.similarity import similarity_score

STAR_CUES = {
    'situation': ['when', 'where', 'team', 'context', 'during'],
    'task': ['responsible', 'role', 'goal', 'task'],
    'action': ['i did', 'i built', 'i decided', 'i implemented', 'i led'],
    'result': ['resulted in', 'improved', 'increased', 'reduced', 'outcome', 'delivered'],
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9']+", (text or '').lower())


def keyword_coverage(reference: str, candidate: str) -> Tuple[float, List[str], List[str]]:
    stop = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'have', 'was', 'were', 'your', 'about', 'what', 'when', 'where', 'their'}
    ref_tokens = [t for t in _tokenize(reference) if len(t) > 2 and t not in stop]
    ref_unique = sorted(set(ref_tokens))
    cand_tokens = set(_tokenize(candidate))
    matched = [token for token in ref_unique if token in cand_tokens]
    missing = [token for token in ref_unique if token not in cand_tokens]
    score = round((len(matched) / max(len(ref_unique), 1)) * 100.0, 2)
    return score, matched, missing[:10]


def completeness_score(reference: str, candidate: str, threshold: float = COMPLETENESS_THRESHOLD) -> Tuple[float, List[str]]:
    points = [p.strip() for p in re.split(r'(?<=[.!?])\s+', reference) if p.strip()]
    if not points:
        return 100.0, []
    covered = 0
    uncovered = []
    for point in points:
        if similarity_score(point, candidate) >= threshold * 100:
            covered += 1
        else:
            uncovered.append(point)
    return round((covered / len(points)) * 100.0, 2), uncovered


def structure_score(candidate: str) -> Tuple[float, List[str], bool]:
    normalized = (candidate or '').lower()
    found = []
    for key, cues in STAR_CUES.items():
        if any(cue in normalized for cue in cues):
            found.append(key)
    missing = [name for name in ['situation', 'task', 'action', 'result'] if name not in found]
    score = round((len(found) / 4) * 100.0, 2)
    return score, missing, len(found) > 0


def score_length(candidate: str, category: str) -> float:
    target_min, target_max = CATEGORY_LENGTH_TARGETS.get(category, (40, 200))
    word_count = len(_tokenize(candidate))
    if word_count < target_min:
        return max(0.0, round(100.0 - ((target_min - word_count) / max(target_min, 1)) * 60.0, 2))
    if word_count > target_max:
        excess = word_count - target_max
        return max(0.0, round(100.0 - (excess / max(target_max, 1)) * 50.0, 2))
    return 100.0


def fluency_score(candidate: str) -> float:
    tokens = _tokenize(candidate)
    if not tokens:
        return 0.0
    filler_words = {'um', 'uh', 'like', 'basically'}
    filler_count = sum(1 for token in tokens if token in filler_words)
    filler_rate = (filler_count / len(tokens)) * 100.0
    sent_count = max(1, len(re.split(r'[.!?]', candidate)))
    avg_sentence_len = sum(len(_tokenize(s)) for s in re.split(r'[.!?]', candidate) if s.strip()) / sent_count
    repeated = sum(1 for token in set(tokens) if tokens.count(token) > 2)
    penalty = filler_rate * 0.7 + max(0, avg_sentence_len - 18) * 2.5 + repeated * 2
    return max(0.0, round(100.0 - penalty, 2))


def evaluate_answer(question: Dict[str, str], candidate: str, category: Optional[str] = None) -> Dict[str, float]:
    reference = question.get('reference_answer', '')
    category = (category or question.get('category') or 'technical').lower()
    relevance = similarity_score(reference, candidate)
    keyword_score, matched, missing = keyword_coverage(reference, candidate)
    completeness, uncovered = completeness_score(reference, candidate)
    structure, missing_structure, _ = structure_score(candidate)
    length_score = score_length(candidate, category)
    fluency = fluency_score(candidate)
    result = {
        'relevance_score': relevance,
        'keyword_coverage': keyword_score,
        'completeness': completeness,
        'structure': structure if category == 'behavioral' else None,
        'length': length_score,
        'fluency': fluency,
        'confidence': None,
        'missing_keywords': missing,
        'gaps': [],
        'matched_keywords': matched,
        'uncovered_points': uncovered,
        'missing_structure': missing_structure,
    }
    if keyword_score > 70 and relevance < 50:
        result['gaps'].append('Keywords present but not explained in context.')
    if len(_tokenize(candidate)) < 10:
        result['gaps'].append('Answer is under the recommended minimum length for this category.')
    return result


def overall_score(signal_values: Dict[str, float]) -> float:
    total = 0.0
    total += signal_values.get('relevance_score', 0) * OVERALL_WEIGHTS['relevance']
    total += signal_values.get('completeness', 0) * OVERALL_WEIGHTS['completeness']
    total += signal_values.get('keyword_coverage', 0) * OVERALL_WEIGHTS['keyword_coverage']
    if signal_values.get('structure') is not None:
        total += signal_values.get('structure', 0) * OVERALL_WEIGHTS['structure']
    total += signal_values.get('length', 0) * OVERALL_WEIGHTS['length']
    return round(max(0.0, min(100.0, total)), 2)
