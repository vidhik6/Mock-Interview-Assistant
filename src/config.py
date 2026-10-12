import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings:
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    TRANSCRIPTION_MODEL = os.getenv('TRANSCRIPTION_MODEL', 'small')
    FEEDBACK_BACKEND = os.getenv('FEEDBACK_BACKEND', 'template')
    SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', str(BASE_DIR / 'data' / 'mock_interview_app.db'))
    DATA_DIR = os.getenv('DATA_DIR', str(BASE_DIR / 'data'))
    MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', 10 * 1024 * 1024))
    MIN_ANSWER_LENGTH = int(os.getenv('MIN_ANSWER_LENGTH', 30))
    MAX_ANSWER_LENGTH = int(os.getenv('MAX_ANSWER_LENGTH', 5000))


settings = Settings()
