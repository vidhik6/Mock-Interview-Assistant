from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

try:
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover
    WhisperModel = None


def _ffmpeg_path() -> str | None:
    system_ffmpeg = shutil.which('ffmpeg')
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def transcribe_audio_upload(audio_bytes: bytes, filename: str = 'audio.wav') -> Dict[str, Any]:
    if not audio_bytes:
        return {'ok': False, 'message': 'No audio data was provided.', 'transcript': '', 'word_timestamps': []}
    ffmpeg = _ffmpeg_path()
    if ffmpeg is None:
        return {'ok': False, 'message': 'Server audio transcription is unavailable because ffmpeg is not installed.', 'transcript': '', 'word_timestamps': []}
    if WhisperModel is None:
        return {'ok': False, 'message': 'Speech model is not available in this environment. Install faster-whisper and a cached model.', 'transcript': '', 'word_timestamps': []}

    tempdir = Path(tempfile.mkdtemp(prefix='mock_interview_'))
    input_path = tempdir / 'input_upload.bin'
    output_path = tempdir / 'converted.wav'
    input_path.write_bytes(audio_bytes)

    try:
        conversion = subprocess.run(
            [ffmpeg, '-y', '-i', str(input_path), '-ar', '16000', '-ac', '1', str(output_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if conversion.returncode != 0 or not output_path.exists():
            return {'ok': False, 'message': 'Audio could not be converted. Make sure the recording format is supported.', 'transcript': '', 'word_timestamps': []}

        model = WhisperModel(os.getenv('TRANSCRIPTION_MODEL', 'small'), device='cpu', compute_type='int8')
        segments, _ = model.transcribe(str(output_path), beam_size=5)
        transcript = ' '.join(seg.text for seg in segments)
        word_timestamps = []
        for seg in segments:
            for word in getattr(seg, 'words', []) or []:
                word_timestamps.append({'word': word.word, 'start': word.start, 'end': word.end})
        return {'ok': True, 'transcript': transcript.strip(), 'word_timestamps': word_timestamps}
    except Exception as exc:
        return {'ok': False, 'message': f'Transcription failed: {exc}', 'transcript': '', 'word_timestamps': []}
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
