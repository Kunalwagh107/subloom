"""Optional real NVIDIA execution checks; explicitly enable SUBLOOM_TEST_GPU=1."""
import os
import threading

import pytest

from subloom.errors import Cancelled
from subloom.hardware import detect
from subloom.media import probe
from subloom.process import run
from subloom.models import ModelManager
from subloom.whisper_engine import WhisperEngine

pytestmark = pytest.mark.skipif(os.environ.get("SUBLOOM_TEST_GPU") != "1", reason="Explicit GPU test opt-in required")


def test_actual_balanced_auto_cuda(tmp_path, model_dir, cancel, speech_corpus):
    speech = speech_corpus / "english.wav"
    if not speech.exists() or not detect().gpu_name or not WhisperEngine.gpu_cli():
        pytest.skip("Local English sample and compatible NVIDIA runtime required")
    engine = WhisperEngine(ModelManager(model_dir), tmp_path)
    media = probe(speech, cancel)
    result = engine.infer(media, media.default_track, "small", "Balanced", "Auto", "en", False, cancel, lambda *_: None)
    assert result and engine.last_backend == "NVIDIA GPU"


def test_actual_cuda_cancellation(tmp_path, model_dir, cancel, speech_corpus, ffmpeg):
    source = speech_corpus / "english.wav"
    if not source.exists() or not detect().gpu_name or not WhisperEngine.gpu_cli():
        pytest.skip("Local English sample and compatible NVIDIA runtime required")
    speech = tmp_path / "cancellation.wav"
    run([ffmpeg, "-v", "error", "-stream_loop", "7", "-i", str(source), "-t", "60", str(speech)], cancel)
    engine = WhisperEngine(ModelManager(model_dir), tmp_path)
    media = probe(speech, cancel)
    timers = []
    def progress(step, _value):
        if step.startswith("Loading model") and not timers:
            timer = threading.Timer(0.25, cancel.cancel)
            timers.append(timer)
            timer.start()
    try:
        with pytest.raises(Cancelled):
            engine.infer(media, media.default_track, "small", "Performance", "GPU", "hi", False, cancel, progress)
        assert not list(tmp_path.glob("asr-*"))
    finally:
        for timer in timers:
            timer.join()
