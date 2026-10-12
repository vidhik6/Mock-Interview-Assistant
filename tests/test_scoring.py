from src.scoring.similarity import map_similarity_to_100
from src.scoring.signals import completeness_score, fluency_score, keyword_coverage, overall_score, score_length, structure_score


def test_similarity_mapping():
    assert map_similarity_to_100(0.5) == 50.0
    assert map_similarity_to_100(-0.2) == 0.0


def test_keyword_coverage_handles_duplicates():
    score, matched, missing = keyword_coverage('I built a scalable API and improved reliability for users.', 'I built a scalable API and a scalable API.')
    assert score > 0
    assert 'api' in matched


def test_completeness_structure_and_fluency():
    comp, _ = completeness_score('I built a dashboard. It improved response time. The team adopted it.', 'I built a dashboard and the team adopted it.')
    assert comp >= 0
    struct, missing, ok = structure_score('I was responsible for building the dashboard. I decided to optimize the queries. The result was faster reporting.')
    assert struct >= 25
    assert 0 <= fluency_score('I like to work with the team and the team works well together.') <= 100


def test_length_and_overall_score_formula():
    assert 0 <= score_length('short answer', 'technical') <= 100
    values = {'relevance_score': 80, 'completeness': 70, 'keyword_coverage': 75, 'structure': 50, 'length': 90}
    result = overall_score(values)
    assert 0 <= result <= 100
