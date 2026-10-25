"""Adapter failure and caching semantics; actual ASR lives in test_asr.py."""
from dataclasses import replace
import json

import pytest

from subloom.errors import GPUError, SubloomError
from subloom.media import AudioTrack, Media
from subloom.models import ModelManager
from subloom.pipeline import generate
from subloom.subtitles import segment
from subloom.whisper_engine import WhisperEngine


@pytest.fixture
def media():
    return Media("test.wav", 3000, None, 0, 0, "0/1", [AudioTrack(0, "pcm_s16le", 16000, 1, "hi", "", True)])


def test_mode_cache_preserves_edits_and_invalidates(tmp_path, media, cancel):
    calls = []
    class TestEngine:
        def infer(self, *args):
            calls.append(args)
            return [segment(0, 1000, "Today" if args[6] else "आज ML")]
    engine = TestEngine()
    settings = {"track": 0, "profile": "Eco", "device": "CPU", "language": "hi"}
    path = tmp_path / "current.json"
    session = generate(media, {"sha256": "one"}, "base", settings, "hinglish", None, engine, path, cancel, lambda *_: None)
    assert len(calls) == 1 and session.raw[0].text == "आज ML"
    session.edits["hinglish"] = [replace(session.raw[0], text="Edited ML")]
    translated = generate(media, session.source, "base", settings, "english", session, engine, path, cancel, lambda *_: None)
    assert len(calls) == 2
    assert translated.raw == session.raw
    again = generate(media, session.source, "base", settings, "hinglish", translated, engine, path, cancel, lambda *_: None)
    assert len(calls) == 2 and again.captions("hinglish")[0].text == "Edited ML"
    generate(media, session.source, "base", {**settings, "language": "auto"}, "original", again, engine, path, cancel, lambda *_: None)
    assert len(calls) == 3


def test_explicit_gpu_does_not_silently_fallback(tmp_path, monkeypatch, media, cancel):
    from subloom.hardware import Hardware
    monkeypatch.setattr("subloom.whisper_engine.detect", lambda: Hardware(8, 16, 8, "Test NVIDIA", 4096, "test"))
    monkeypatch.setattr("subloom.whisper_engine.verify", lambda *_: None)
    engine = WhisperEngine(ModelManager(tmp_path), tmp_path)
    monkeypatch.setattr(engine, "gpu_cli", lambda: tmp_path / "cuda-cli.exe")
    calls = []
    def fail_gpu(*args):
        calls.append(args[6])
        if args[6]:
            raise SubloomError("CUDA device error")
        return [segment(0, 1000, "CPU result")]
    monkeypatch.setattr(engine, "_infer", fail_gpu)
    with pytest.raises(GPUError, match="Retry on CPU"):
        engine.infer(media, 0, "base", "Performance", "GPU", "hi", False, cancel, lambda *_: None)
    assert calls == [True]
    calls.clear()
    result = engine.infer(media, 0, "base", "Performance", "Auto", "hi", False, cancel, lambda *_: None)
    assert calls == [True, False] and result[0].text == "CPU result"


def test_balanced_auto_uses_gpu_without_switching_model(tmp_path, monkeypatch, media, cancel):
    from subloom.hardware import Hardware
    monkeypatch.setattr("subloom.whisper_engine.detect", lambda: Hardware(8, 16, 8, "Test NVIDIA", 4096, "test"))
    monkeypatch.setattr("subloom.whisper_engine.verify", lambda *_: None)
    engine = WhisperEngine(ModelManager(tmp_path), tmp_path)
    monkeypatch.setattr(engine, "gpu_cli", lambda: tmp_path / "cuda.exe")
    calls = []
    def infer(*args):
        calls.append((args[2], args[6]))
        return [segment(0, 1000, "local result")]
    monkeypatch.setattr(engine, "_infer", infer)
    engine.infer(media, 0, "small", "Balanced", "Auto", "hi", False, cancel, lambda *_: None)
    assert calls == [("small", True)]
    calls.clear()
    engine.infer(media, 0, "small", "Eco", "Auto", "hi", False, cancel, lambda *_: None)
    assert calls == [("small", False)]


def test_completed_chunks_resume_after_cancel_and_fast_mode_invalidates(tmp_path, monkeypatch, media, cancel):
    from subloom.errors import Cancelled
    from subloom.process import Cancellation
    import subloom.whisper_engine as module
    monkeypatch.setattr(module, "CHUNK_MS", 1000)
    monkeypatch.setattr(module, "OVERLAP_MS", 100)
    starts = []
    monkeypatch.setattr(module, "prepare_audio", lambda _m, _t, _d, start, *_a: starts.append(start))
    monkeypatch.setattr(module, "executable", lambda _: "whisper-cli")
    engine = WhisperEngine(ModelManager(tmp_path), tmp_path, {"sha256": "recording", "bytes": 99})
    monkeypatch.setattr(engine, "validate_cli", lambda *_: None)
    calls = 0
    arguments_seen = []
    def cli(_args, token, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise Cancelled("stopped second chunk")
        work = kwargs["cwd"]
        arguments_seen.append((work / "arguments.txt").read_text(encoding="utf-8"))
        (work / "result.json").write_text(json.dumps({"model": {"multilingual": True}, "transcription": [
            {"offsets": {"from": 100, "to": 800}, "text": "completed chunk"}]}))
        return ""
    monkeypatch.setattr(module, "run", cli)
    with pytest.raises(Cancelled):
        engine._infer(media, 0, "base", "Balanced", "hi", False, False, cancel, lambda *_: None)
    saved = json.loads((tmp_path / "inference.checkpoint.json").read_text())
    assert saved["completed_ms"] == 1000
    starts.clear()
    result = engine._infer(media, 0, "base", "Balanced", "hi", False, False, Cancellation(), lambda *_: None)
    assert starts == [900, 1900] and len(result) == 3
    assert "--beam-size" not in arguments_seen[-1]
    engine.fast_decode = True
    starts.clear()
    engine._infer(media, 0, "base", "Balanced", "hi", False, False, Cancellation(), lambda *_: None)
    assert starts[0] == 0
    assert "--beam-size\n1\n--best-of\n1" in arguments_seen[-1]


def test_chunk_offsets_and_boundary_ownership(tmp_path, monkeypatch, media, cancel):
    import subloom.whisper_engine as module
    monkeypatch.setattr(module, "CHUNK_MS", 1000)
    monkeypatch.setattr(module, "OVERLAP_MS", 100)
    monkeypatch.setattr(module, "prepare_audio", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "executable", lambda _: "whisper-cli")
    engine = WhisperEngine(ModelManager(tmp_path), tmp_path)
    monkeypatch.setattr(engine, "validate_cli", lambda *_: None)
    count = 0
    def fake_cli(args, *_a, **_k):
        nonlocal count
        count += 1
        work = _k["cwd"]
        arguments = (work / "arguments.txt").read_text(encoding="utf-8").splitlines()
        output = (work / arguments[arguments.index("--output-file") + 1]).with_suffix(".json")
        # Per-chunk offsets are relative to its 100 ms context region.
        output.write_text(json.dumps({"model": {"multilingual": True}, "transcription": [
            {"offsets": {"from": 100 if count > 1 else 0, "to": 900}, "text": f"Chunk {count}"}]}))
        return ""
    monkeypatch.setattr(module, "run", fake_cli)
    items = engine._infer(media, 0, "base", "Eco", "hi", False, False, cancel, lambda *_: None)
    assert [s.start_ms for s in items] == [0, 1000, 2000]
    assert len({s.id for s in items}) == 3
