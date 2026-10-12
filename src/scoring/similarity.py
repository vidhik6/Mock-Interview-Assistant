from __future__ import annotations

import re
from typing import List


def normalize_text(text: str) -> str:
    text = (text or '').lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def tokenise(text: str) -> List[str]:
    return normalize_text(text).split()


def semantic_similarity(a: str, b: str, model_name: str = 'all-MiniLM-L6-v2') -> float:
    a_tokens = set(tokenise(a))
    b_tokens = set(tokenise(b))
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    if union == 0:
        return 0.0
    jaccard = inter / union
    score = 0.65 * jaccard + 0.35 * min(len(a_tokens & b_tokens), 10) / 10.0
    return max(0.0, min(1.0, score))


def map_similarity_to_100(score_0_1: float) -> float:
    clipped = max(-1.0, min(1.0, score_0_1))
    if clipped < 0:
        return 0.0
    return round(clipped * 100.0, 2)


def similarity_score(reference: str, candidate: str, model_name: str = 'all-MiniLM-L6-v2') -> float:
    sim = semantic_similarity(reference, candidate, model_name)
    return map_similarity_to_100(sim)
