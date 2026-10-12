from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import sqlite3

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.config import settings
from src.scoring.feedback import generate_feedback
from src.scoring.signals import evaluate_answer
from src.speech.transcribe import transcribe_audio_upload
from src.storage import (
    create_session,
    create_auth_session,
    create_user,
    delete_auth_session,
    delete_session,
    authenticate_user,
    export_session,
    fetch_question_page,
    fetch_session,
    get_question_by_id,
    init_db,
    get_user_by_token,
    list_sessions,
    list_session_summaries,
    save_attempt,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))
app = FastAPI(title='Mock Interview Assistant')
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')

init_db()


@app.middleware('http')
async def attach_user(request: Request, call_next):
    request.state.user = get_user_by_token(request.cookies.get('auth_token'))
    return await call_next(request)


class SessionPayload(BaseModel):
    category: Optional[str] = None


class AnswerPayload(BaseModel):
    question_id: str
    text: Optional[str] = None
    audio_id: Optional[str] = None
    transcript: Optional[str] = None


class AuthPayload(BaseModel):
    username: str
    password: str


def require_user(request: Request) -> Dict[str, Any]:
    user = request.state.user
    if not user:
        raise HTTPException(status_code=401, detail={'error': 'authentication_required', 'message': 'Log in to continue.'})
    return user


def set_auth_cookie(response: Response, user_id: int) -> None:
    response.set_cookie('auth_token', create_auth_session(user_id), httponly=True, samesite='lax', max_age=60 * 60 * 24 * 30)


@app.get('/api/health')
def health() -> Dict[str, Any]:
    return {
        'status': 'ok',
        'models': {
            'embedding_model': settings.EMBEDDING_MODEL,
            'transcription_model': settings.TRANSCRIPTION_MODEL,
            'feedback_backend': settings.FEEDBACK_BACKEND,
        },
    }


@app.get('/api/auth/me')
def auth_me(request: Request):
    return {'user': request.state.user}


@app.post('/api/auth/register')
def register(payload: AuthPayload, response: Response):
    username = payload.username.strip()
    if len(username) < 3 or len(username) > 40:
        raise HTTPException(status_code=400, detail={'error': 'invalid_username', 'message': 'Username must be 3 to 40 characters.'})
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail={'error': 'weak_password', 'message': 'Password must be at least 8 characters.'})
    try:
        user_id = create_user(username, payload.password)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail={'error': 'username_taken', 'message': 'That username is already registered.'})
    set_auth_cookie(response, user_id)
    return {'user': {'id': user_id, 'username': username}}


@app.post('/api/auth/login')
def login(payload: AuthPayload, response: Response):
    user = authenticate_user(payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail={'error': 'invalid_credentials', 'message': 'Username or password is incorrect.'})
    set_auth_cookie(response, user['id'])
    return {'user': user}


@app.post('/api/auth/logout')
def logout(request: Request, response: Response):
    delete_auth_session(request.cookies.get('auth_token'))
    response.delete_cookie('auth_token')
    return {'ok': True}


@app.get('/api/questions')
def get_questions(
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    data = fetch_question_page(category=category, subcategory=subcategory, q=q, limit=limit, offset=offset)
    return {'items': data, 'count': len(data), 'offset': offset, 'limit': limit}


@app.get('/api/questions/{question_id}')
def get_question(question_id: str):
    q = get_question_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail={'error': 'question_not_found', 'message': 'Question not found.'})
    row = dict(q)
    row.pop('reference_answer', None)
    return row


@app.post('/api/sessions')
def start_session(request: Request, payload: SessionPayload):
    user = require_user(request)
    return {'session_id': create_session(payload.category, user['id'])}


@app.post('/api/sessions/{session_id}/answers')
def submit_answer(request: Request, session_id: str, payload: AnswerPayload):
    user = require_user(request)
    if not fetch_session(session_id, user['id']):
        raise HTTPException(status_code=404, detail={'error': 'session_not_found', 'message': 'Session not found.'})
    answer_text = (payload.text or payload.transcript or '').strip()
    if not answer_text:
        raise HTTPException(status_code=400, detail={'error': 'empty_answer', 'message': 'Provide a text answer or transcript.'})
    if len(answer_text) < settings.MIN_ANSWER_LENGTH:
        raise HTTPException(status_code=400, detail={'error': 'answer_too_short', 'message': f'Answer must be at least {settings.MIN_ANSWER_LENGTH} characters.'})
    if len(answer_text) > settings.MAX_ANSWER_LENGTH:
        raise HTTPException(status_code=400, detail={'error': 'answer_too_long', 'message': f'Answer must be under {settings.MAX_ANSWER_LENGTH} characters.'})
    question = get_question_by_id(payload.question_id)
    if not question:
        raise HTTPException(status_code=404, detail={'error': 'question_not_found', 'message': 'Question not found.'})
    result = evaluate_answer(question, answer_text, category=question.get('category'))
    feedback = generate_feedback(result)
    feedback['transcript'] = payload.transcript or None
    save_attempt(session_id, payload.question_id, json.dumps(feedback), question.get('category'), answer_text)
    return feedback


@app.post('/api/transcribe')
async def transcribe_upload(file: UploadFile = File(...)):
    if file.size and file.size > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail={'error': 'upload_too_large', 'message': f'Upload exceeds {settings.MAX_UPLOAD_BYTES} bytes.'})
    payload = await file.read()
    result = transcribe_audio_upload(payload, filename=file.filename or 'upload.wav')
    if not result.get('ok'):
        raise HTTPException(status_code=400, detail={'error': 'transcription_failed', 'message': result.get('message', 'Transcription failed.')})
    return result


@app.get('/api/sessions/{session_id}')
def session_detail(request: Request, session_id: str):
    user = require_user(request)
    data = fetch_session(session_id, user['id'])
    if not data:
        raise HTTPException(status_code=404, detail={'error': 'session_not_found', 'message': 'Session not found.'})
    return data


@app.get('/api/sessions/{session_id}/export')
def export_session_file(request: Request, session_id: str, format: str = 'json'):
    user = require_user(request)
    if format not in {'json', 'csv'}:
        raise HTTPException(status_code=400, detail={'error': 'unsupported_format', 'message': 'Use format=json or format=csv.'})
    path = export_session(session_id, format, user['id'])
    return FileResponse(path, filename=f'session_{session_id}.{format}')


@app.delete('/api/sessions/{session_id}')
def delete_session_route(request: Request, session_id: str):
    user = require_user(request)
    if not delete_session(session_id, user['id']):
        raise HTTPException(status_code=404, detail={'error': 'session_not_found', 'message': 'Session not found.'})
    return {'ok': True}


@app.get('/')
def home(request: Request):
    return templates.TemplateResponse('home.html', {'request': request})


@app.get('/practice')
def practice(request: Request):
    if not request.state.user:
        return RedirectResponse('/login?next=/practice', status_code=303)
    return templates.TemplateResponse('practice.html', {'request': request})


@app.get('/history')
def history(request: Request):
    if not request.state.user:
        return RedirectResponse('/login?next=/history', status_code=303)
    return templates.TemplateResponse('history.html', {'request': request, 'sessions': list_session_summaries(request.state.user['id'])})


@app.get('/methodology')
def methodology(request: Request):
    return templates.TemplateResponse('methodology.html', {'request': request})


@app.get('/session-summary')
def session_summary_page(request: Request):
    if not request.state.user:
        return RedirectResponse('/login?next=/session-summary', status_code=303)
    sessions = list_sessions(request.state.user['id'])
    return templates.TemplateResponse(
        'session_summary.html',
        {
            'request': request,
            'latest_session_id': sessions[0]['id'] if sessions else None,
        },
    )


@app.get('/login')
def login_page(request: Request):
    if request.state.user:
        return RedirectResponse('/practice', status_code=303)
    return templates.TemplateResponse('login.html', {'request': request})


@app.get('/demo')
def demo_page():
    return HTMLResponse('<html><body><h1>Demo page</h1><p>Use the same scoring functions through Gradio if installed.</p></body></html>')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)
