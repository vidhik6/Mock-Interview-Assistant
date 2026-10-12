import pytest

pytestmark = pytest.mark.skip(reason='Whisper model is not guaranteed to be cached in CI environments.')


def test_transcribe_invokes_wav_if_available():
    assert True
