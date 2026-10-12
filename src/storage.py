import json
import ast
import hashlib
import hmac
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings
from src.data.loaders import load_questions

DB_PATH = Path(settings.SQLITE_DB_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            category TEXT,
            metadata TEXT DEFAULT '{}',
            user_id INTEGER
        )
    ''')
    session_columns = {row['name'] for row in conn.execute('PRAGMA table_info(sessions)').fetchall()}
    if 'user_id' not in session_columns:
        conn.execute('ALTER TABLE sessions ADD COLUMN user_id INTEGER')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question_id TEXT,
            category TEXT,
            answer TEXT,
            score TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 240_000)
    return f'{salt.hex()}:{digest.hex()}'


def _check_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split(':', 1)
        expected = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt_hex), 240_000).hex()
        return hmac.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False


def create_user(username: str, password: str) -> int:
    conn = connect_db()
    try:
        cursor = conn.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, _hash_password(password)),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    conn = connect_db()
    row = conn.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if not row or not _check_password(password, row['password_hash']):
        return None
    return {'id': row['id'], 'username': row['username']}


def create_auth_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = connect_db()
    conn.execute('INSERT INTO auth_sessions (token, user_id) VALUES (?, ?)', (token, user_id))
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    conn = connect_db()
    row = conn.execute('''
        SELECT u.id, u.username
        FROM auth_sessions a
        JOIN users u ON u.id = a.user_id
        WHERE a.token = ?
    ''', (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_auth_session(token: Optional[str]) -> None:
    if not token:
        return
    conn = connect_db()
    conn.execute('DELETE FROM auth_sessions WHERE token = ?', (token,))
    conn.commit()
    conn.close()


def create_session(category: Optional[str] = None, user_id: Optional[int] = None) -> str:
    sid = uuid.uuid4().hex
    conn = connect_db()
    conn.execute('INSERT INTO sessions (id, category, user_id) VALUES (?, ?, ?)', (sid, category, user_id))
    conn.commit()
    conn.close()
    return sid


def save_attempt(session_id: str, question_id: str, score: str, category: Optional[str], answer: str) -> None:
    conn = connect_db()
    conn.execute(
        'INSERT INTO attempts (session_id, question_id, category, answer, score) VALUES (?, ?, ?, ?, ?)',
        (session_id, question_id, category, answer, score),
    )
    conn.commit()
    conn.close()


def fetch_question_page(category=None, subcategory=None, q=None, limit=20, offset=0):
    rows = load_questions(Path(settings.DATA_DIR) / 'questions.csv')
    filtered = []
    for row in rows:
        if category and row.get('category') != category:
            continue
        if subcategory and row.get('subcategory') != subcategory:
            continue
        if q and q.lower() not in (row.get('question') or '').lower():
            continue
        filtered.append({
            'id': row.get('id'),
            'category': row.get('category'),
            'subcategory': row.get('subcategory'),
            'question': row.get('question'),
            'difficulty': row.get('difficulty'),
        })
    return filtered[offset: offset + limit]


def get_question_by_id(question_id: str):
    rows = load_questions(Path(settings.DATA_DIR) / 'questions.csv')
    for row in rows:
        if row.get('id') == question_id:
            return row
    return None


def fetch_session(session_id: str, user_id: Optional[int] = None):
    conn = connect_db()
    session = conn.execute('SELECT * FROM sessions WHERE id = ? AND user_id = ?', (session_id, user_id)).fetchone()
    if not session:
        conn.close()
        return None
    attempts = conn.execute('SELECT * FROM attempts WHERE session_id = ? ORDER BY created_at', (session_id,)).fetchall()
    conn.close()
    return {'session_id': session['id'], 'category': session['category'], 'attempts': [dict(a) for a in attempts]}


def list_sessions(user_id: int) -> List[Dict[str, Any]]:
    conn = connect_db()
    rows = conn.execute('SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_session_summaries(user_id: int) -> List[Dict[str, Any]]:
    conn = connect_db()
    rows = conn.execute('''
        SELECT
            s.id,
            s.created_at,
            s.category,
            COUNT(a.id) AS attempt_count,
            GROUP_CONCAT(a.score, '|||') AS scores
        FROM sessions s
        LEFT JOIN attempts a ON a.session_id = s.id
        WHERE s.user_id = ?
        GROUP BY s.id
        ORDER BY s.created_at DESC
    ''', (user_id,)).fetchall()
    conn.close()

    summaries = []
    for row in rows:
        scores = []
        for raw_score in (row['scores'] or '').split('|||'):
            if not raw_score:
                continue
            try:
                scores.append(json.loads(raw_score))
            except json.JSONDecodeError:
                try:
                    scores.append(ast.literal_eval(raw_score))
                except (ValueError, SyntaxError):
                    continue
        overall_scores = [float(score.get('overall_score', 0)) for score in scores]
        latest = scores[-1] if scores else {}
        focus = latest.get('priority_improvement') or {}
        summaries.append({
            'id': row['id'],
            'created_at': row['created_at'],
            'category': row['category'],
            'attempt_count': row['attempt_count'],
            'average_score': round(sum(overall_scores) / len(overall_scores), 1) if overall_scores else None,
            'latest_score': round(float(latest.get('overall_score', 0)), 1) if latest else None,
            'focus_dimension': focus.get('dimension'),
            'focus_score': round(float(focus.get('score', 0)), 1) if focus else None,
        })
    return summaries


def delete_session(session_id: str, user_id: int) -> bool:
    conn = connect_db()
    session = conn.execute('SELECT id FROM sessions WHERE id = ? AND user_id = ?', (session_id, user_id)).fetchone()
    if not session:
        conn.close()
        return False
    conn.execute('DELETE FROM attempts WHERE session_id = ?', (session_id,))
    cursor = conn.execute('DELETE FROM sessions WHERE id = ? AND user_id = ?', (session_id, user_id))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def export_session(session_id: str, fmt: str, user_id: int) -> str:
    data = fetch_session(session_id, user_id)
    if not data:
        raise FileNotFoundError('Session not found')
    path = Path(settings.DATA_DIR) / f'{session_id}.{fmt}'
    if fmt == 'json':
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    else:
        import csv
        with path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['session_id', 'question_id', 'category', 'answer', 'score'])
            for attempt in data['attempts']:
                writer.writerow([session_id, attempt['question_id'], attempt['category'], attempt['answer'], attempt['score']])
    return str(path)
