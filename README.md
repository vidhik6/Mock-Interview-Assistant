# Mock Interview Assistant

A FastAPI-based mock interview practice app that uses semantic similarity, structured signal scoring, and actionable feedback for technical, HR, and behavioral interviews.

## Design decisions
- The app keeps the evaluation logic pure and testable outside the web server.
- The question bank includes the bundled supplemental set and a lightweight local seed set, plus optional public sources when available.
- The default pipeline is CPU-friendly and does not download large models during normal test runs.
- Audio transcription is optional and only runs when a valid audio upload is supplied.
- Browser speech recognition can provide a transcript when server-side audio conversion is unavailable. For server transcription, install `ffmpeg` and ensure the configured Whisper model is available.
- Voice input uses the browser Web Speech API with `en-IN` as the default language. It requires a supported browser and microphone permission; localhost is allowed for local development. Chrome/Edge generally provide the most consistent support, while unsupported browsers can still use typed answers.

## Setup
```bash
pip install -r requirements.txt
python scripts/build_dataset.py
uvicorn main:app --reload
```

## Commands
- `python scripts/build_dataset.py`
- `uvicorn main:app --reload`
- `pytest`
- `python eval/make_test_set.py`

## Scoring formula
The relevance score is computed by mapping the sentence similarity result `c` into 0..100 with `clip(c, 0, 1) * 100`.
The overall score is a weighted sum of relevance, completeness, keyword coverage, structure, and length.
Feedback also identifies the lowest-scoring dimension as the priority improvement and returns missing concepts, uncovered reference points, and targeted suggestions.

## Privacy note
Session metadata, answers, and score history are stored in SQLite at `data/mock_interview_app.db`. Audio is only kept temporarily for transcription and is deleted immediately after processing unless configured otherwise.

## Architecture
```text
Browser -> FastAPI -> SQLite
                      -> scoring engine -> feedback generator
                      -> transcription service -> transcript
                      -> question dataset -> practice questions
```
