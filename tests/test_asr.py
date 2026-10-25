"""Actual CPU inference tests. No ASR mocking. Never downloads from a test."""
import os

import pytest

from subloom.media import probe
from subloom.models import ModelManager
from subloom.pipeline import generate
from subloom.session import identity
from subloom.whisper_engine import WhisperEngine


@pytest.mark.asr
def test_actual_unicode_model_and_cache_paths(tmp_path, model_dir, ffmpeg, cancel, speech_corpus):
    source = speech_corpus / "english.wav"
    if not source.exists() or not ModelManager(model_dir).installed("base"):
        pytest.skip("Requires generated English speech and local Base model")
    folder = tmp_path / "मॉडल with spaces"
    folder.mkdir()
    try:
        os.link(model_dir / "ggml-base.bin", folder / "ggml-base.bin")
    except OSError:
        import shutil
        shutil.copy2(model_dir / "ggml-base.bin", folder / "ggml-base.bin")
    media = probe(source, cancel)
    engine = WhisperEngine(ModelManager(folder), tmp_path / "कैश with spaces")
    result = engine.infer(media, media.default_track, "base", "Eco", "CPU", "en", False, cancel, lambda *_: None)
    assert result and "neural" in " ".join(s.text.lower() for s in result)


@pytest.mark.asr
@pytest.mark.parametrize("name", ["english", "hindi", "hinglish"])
def test_actual_cpu_transcription_and_translation(tmp_path, model_dir, ffmpeg, cancel, monkeypatch, name, speech_corpus):
    corpus = speech_corpus
    path = corpus / (name + ".wav")
    if not path.exists():
        pytest.skip("Generate synthetic licensed fixtures with scripts/make_speech_fixtures.py")
    def network_forbidden(*_a, **_k):
        raise AssertionError("Inference must never access the network")
    monkeypatch.setattr("urllib.request.urlopen", network_forbidden)
    import socket
    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    media = probe(path, cancel)
    source = identity(path, cancel)
    settings = {"track": media.default_track, "profile": "Eco", "device": "CPU", "language": "en" if name == "english" else "hi"}
    model_id = os.environ.get("SUBLOOM_TEST_MODEL", "base")
    if not ModelManager(model_dir).installed(model_id):
        pytest.skip(f"Install local multilingual {model_id} model first")
    engine = WhisperEngine(ModelManager(model_dir), tmp_path / "cache")
    session = generate(media, source, model_id, settings, "hinglish", None, engine,
                       tmp_path / "current.session.json", cancel, lambda *_: None)
    assert session.raw and session.generated["hinglish"]
    for item in session.raw:
        item.validate(media.duration_ms)
    # Cached modes cannot trigger a second ASR process.
    original_infer = engine.infer
    monkeypatch.setattr(engine, "infer", lambda *_a, **_k: pytest.fail("Cached mode reran inference"))
    cached = generate(media, source, model_id, settings, "original", session, engine,
                      tmp_path / "current.session.json", cancel, lambda *_: None)
    assert cached.raw == session.raw
    monkeypatch.setattr(engine, "infer", original_infer)
    translated = generate(media, source, model_id, settings, "english", session, engine,
                          tmp_path / "current.session.json", cancel, lambda *_: None)
    assert translated.generated["english"]
    assert all(not any("\u0900" <= char <= "\u097f" for char in s.text) for s in translated.generated["english"])
    for item in translated.generated["english"]:
        item.validate(media.duration_ms)
