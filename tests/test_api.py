from fastapi.testclient import TestClient
from uuid import uuid4

from main import app

client = TestClient(app)


def login():
    response = client.post('/api/auth/register', json={'username': f'test_{uuid4().hex[:8]}', 'password': 'password123'})
    assert response.status_code == 200


def test_get_health():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert 'status' in r.json()


def test_questions_api():
    r = client.get('/api/questions?limit=5')
    assert r.status_code == 200
    assert 'items' in r.json()


def test_session_creation_and_answer_submission():
    login()
    s = client.post('/api/sessions', json={'category': 'technical'})
    assert s.status_code == 200
    session_id = s.json()['session_id']
    q = client.get('/api/questions?limit=1').json()['items'][0]
    r = client.post(f'/api/sessions/{session_id}/answers', json={'question_id': q['id'], 'text': 'I built a clean API with clear endpoints and performance tuning to improve reliability and speed for users.'})
    assert r.status_code == 200
    assert 'overall_score' in r.json()


def test_bad_answer_length():
    login()
    s = client.post('/api/sessions', json={'category': 'technical'})
    sid = s.json()['session_id']
    q = client.get('/api/questions?limit=1').json()['items'][0]
    r = client.post(f'/api/sessions/{sid}/answers', json={'question_id': q['id'], 'text': 'short'})
    assert r.status_code == 400


def test_session_delete_requires_owner():
    login()
    session_id = client.post('/api/sessions', json={'category': 'hr'}).json()['session_id']
    assert client.delete(f'/api/sessions/{session_id}').status_code == 200
    assert client.get(f'/api/sessions/{session_id}').status_code == 404
