from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from src.scoring.signals import overall_score


def _score_label(score: float) -> str:
    if score >= 85:
        return 'Excellent'
    if score >= 70:
        return 'Strong'
    if score >= 50:
        return 'Developing'
    return 'Needs work'


def _priority(scores: Dict[str, Any]) -> Dict[str, Any]:
    dimensions = {
        'relevance': scores.get('relevance_score', 0),
        'completeness': scores.get('completeness', 0),
        'keyword coverage': scores.get('keyword_coverage', 0),
        'length': scores.get('length', 0),
    }
    if scores.get('structure') is not None:
        dimensions['STAR structure'] = scores.get('structure', 0)
    name, score = min(dimensions.items(), key=lambda item: item[1])
    return {'dimension': name, 'score': round(float(score), 2), 'label': _score_label(float(score))}


def _default_strengths(scores: Dict[str, Any]) -> List[str]:
    strengths = []
    if scores.get('relevance_score', 0) >= 70:
        strengths.append('Your answer stays close to the key idea behind the question.')
    if scores.get('keyword_coverage', 0) >= 60:
        strengths.append('You include several relevant concepts from the expected answer.')
    if scores.get('completeness', 0) >= 70:
        strengths.append('You cover the main points in a clear and coherent way.')
    if scores.get('structure') and scores.get('structure', 0) >= 60:
        strengths.append('Your answer shows recognizable STAR-style structure.')
    if not strengths:
        strengths.append('You communicate the main idea, but the answer would benefit from more specificity.')
    return strengths


def _default_gaps(scores: Dict[str, Any]) -> List[str]:
    gaps = []
    if scores.get('relevance_score', 0) < 70:
        gaps.append('The answer should stay more tightly aligned with the question topic.')
    if scores.get('keyword_coverage', 0) < 60:
        gaps.append('Important concepts are missing: ' + ', '.join(scores.get('missing_keywords', [])[:3]))
    if scores.get('completeness', 0) < 60:
        gaps.append('One or more key points from the model answer are not covered.')
    if scores.get('structure') is not None and scores.get('structure', 100) < 75:
        gaps.append('Add clearer Situation, Task, Action, and Result language to improve structure.')
    if scores.get('length', 100) < 70:
        gaps.append('Expand the answer with more concrete examples and measurable impact.')
    return gaps


def _default_suggestions(scores: Dict[str, Any]) -> List[str]:
    suggestions = []
    if scores.get('missing_keywords'):
        suggestions.append('Add specifics around: ' + ', '.join(scores.get('missing_keywords')[:3]))
    if scores.get('structure') is not None:
        suggestions.append('Use a short STAR outline: situation, task, action, then a measurable result.')
    else:
        suggestions.append('Lead with your approach, then explain the tradeoff or example that supports it.')
    suggestions.append('Give one concrete example or metric showing the outcome of your work.')
    return suggestions


def generate_feedback(scores: Dict[str, Any]) -> Dict[str, Any]:
    overall = overall_score(scores)
    priority = _priority(scores)
    feedback = {
        'overall_score': overall,
        'overall_label': _score_label(overall),
        'priority_improvement': priority,
        'relevance_score': round(float(scores.get('relevance_score', 0)), 2),
        'keyword_coverage': round(float(scores.get('keyword_coverage', 0)), 2),
        'completeness': round(float(scores.get('completeness', 0)), 2),
        'structure': round(float(scores.get('structure', 0)), 2) if scores.get('structure') is not None else None,
        'length': round(float(scores.get('length', 0)), 2),
        'fluency': round(float(scores.get('fluency', 0)), 2),
        'confidence': None,
        'strengths': _default_strengths(scores),
        'gaps': list(scores.get('gaps', [])) or _default_gaps(scores),
        'suggestions': _default_suggestions(scores),
        'missing_keywords': list(scores.get('missing_keywords', [])),
        'uncovered_points': list(scores.get('uncovered_points', [])),
        'missing_structure': list(scores.get('missing_structure', [])),
        'transcript': None,
    }
    if os.getenv('FEEDBACK_BACKEND', 'template') == 'llm':
        try:
            import openai  # type: ignore
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                response = openai.OpenAI(api_key=api_key).chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[{'role': 'system', 'content': 'Return JSON with strengths, gaps, and suggestions.'}, {'role': 'user', 'content': json.dumps(scores)}],
                    response_format={'type': 'json_object'},
                )
                parsed = json.loads(response.choices[0].message.content)
                feedback.update(parsed)
                return feedback
        except Exception:
            pass
    return feedback
