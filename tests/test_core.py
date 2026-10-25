from dataclasses import replace
import html
import sys
import time

import pytest
import pysubs2

from subloom.errors import Cancelled, SubloomError
from subloom.hardware import Hardware, compatibility, threads
from subloom.language import hinglish, romanize
from subloom.process import Cancellation, run
from subloom.session import Session, atomic_json, cache_key, identity, load_session
from subloom.subtitles import export_text, parse_time, render, segment, timestamp
from subloom.whisper_engine import parse_output


def test_subtitle_roundtrip(tmp_path):
    items = [segment(1234, 5000, "Edited Hindi हिन्दी & English\nsecond line"), segment(6200, 7900, "neural networks")]
    for fmt in ("srt", "vtt"):
        target = tmp_path / f"字幕.{fmt}"
        export_text(items, target, fmt)
        parsed = pysubs2.load(str(target), encoding="utf-8")
        assert [(x.start, x.end, html.unescape(x.plaintext)) for x in parsed] == [(s.start_ms, s.end_ms, s.text) for s in items]
    text = tmp_path / "out.txt"
    export_text(items, text, "txt", timed_text=True)
    assert "[00:00:01.234]" in text.read_text(encoding="utf-8")
    assert "हिन्दी" in text.read_text(encoding="utf-8")


def test_no_overwrite(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original")
    with pytest.raises(SubloomError, match="Original media"):
        export_text([], source, "srt", source)
    with pytest.raises(SubloomError, match="already exists"):
        export_text([], source, "srt")
    assert source.read_bytes() == b"original"


@pytest.mark.parametrize("start,end", [(-1, 100), (100, 100), (101, 100), (0, 1001)])
def test_invalid_timing(start, end):
    with pytest.raises(SubloomError):
        segment(start, end, "test").validate(1000)


def test_times_and_literal_subtitle_text():
    assert parse_time("01:02:03.456") == 3723456
    assert timestamp(3723456) == "01:02:03,456"
    assert parse_time("100:02:03,456") == 360123456
    for bad in ("01:99:00.000", "-1", "00:00:00", "nan"):
        with pytest.raises(SubloomError):
            parse_time(bad)
    output = render([segment(0, 10, "<script> & test\n\nextra")], "vtt")
    assert "&lt;script&gt; &amp;" in output
    assert "test\n\nextra" not in output


def test_romanization():
    assert romanize("आज हम neural networks समझेंगे") == "aaj hum neural networks samjhenge"
    assert romanize("Aaj hum PyTorch v2.3 API samjhenge") == "Aaj hum PyTorch v2.3 API samjhenge"
    assert romanize("नमस्ते दुनिया, यह हिंदी है।") == "namaste duniya, yeh Hindi hai."
    assert romanize("भारत में १२३ datasets") == "bhaarat mein 123 datasets"
    source = [segment(10, 100, "आज ML")]
    converted = hinglish(source)
    assert converted[0].id == source[0].id and converted[0].start_ms == 10
    assert source[0].text == "आज ML"


def test_session_identity_snapshots_and_cache(tmp_path, cancel):
    media = tmp_path / "recording.wav"
    media.write_bytes(b"one")
    first = identity(media, cancel)
    key = cache_key(first, "base", "hash", {"track": 0})
    session = Session(first, 1000, "base", {"track": 0}, key)
    session.raw = [segment(10, 500, "raw")]
    session.generated["original"] = list(session.raw)
    session.edits["original"] = [replace(session.raw[0], text="edited")]
    target = tmp_path / "current.session.json"
    atomic_json(target, session.to_dict())
    restored = load_session(target)
    assert restored.raw[0].text == "raw"
    assert restored.captions("original")[0].text == "edited"
    assert cache_key(first, "small", "hash", {"track": 0}) != key
    assert cache_key(first, "base", "hash", {"track": 1}) != key
    media.write_bytes(b"two")
    assert identity(media, cancel)["sha256"] != first["sha256"]
    assert not list(tmp_path.glob(".save-*"))
    data = session.to_dict()
    data["edits"]["original"][0]["end_ms"] = 2000
    with pytest.raises(SubloomError):
        Session.from_dict(data)


def test_corrupt_session_is_preserved(tmp_path):
    path = tmp_path / "session.json"
    path.write_text("bad")
    with pytest.raises(SubloomError):
        load_session(path)
    assert path.read_text() == "bad"


def test_changed_source_rejected_and_previous_snapshot_preserved(tmp_path, cancel):
    from subloom.session import assert_source_unchanged, save_session
    source = tmp_path / "recording.wav"
    source.write_bytes(b"recording")
    fingerprint = identity(source, cancel)
    assert_source_unchanged(fingerprint)
    current = Session(fingerprint, 1000, "base", {}, "one")
    target = tmp_path / "current.session.json"
    save_session(target, current)
    save_session(target, replace(current, key="two"))
    assert load_session(tmp_path / "previous.session.json").key == "one"
    source.write_bytes(b"changed recording")
    with pytest.raises(SubloomError, match="changed after import"):
        assert_source_unchanged(fingerprint)


def test_hardware_profiles():
    for profile in ("Eco", "Balanced", "Performance"):
        assert 1 <= threads(profile, 2) <= 2
        assert 1 <= threads(profile, 128) <= 16
    assert compatibility("medium", Hardware(4, 8, 2))[0] == "Not enough memory"
    assert compatibility("small", Hardware(8, 16, 8))[0] == "Recommended"


def test_json_timestamps_are_milliseconds():
    data = {"model": {"multilingual": True}, "transcription": [{"offsets": {"from": 100, "to": 950}, "text": " नमस्ते "}]}
    items = parse_output(data, 1500, 200)
    assert (items[0].start_ms, items[0].end_ms, items[0].text) == (300, 1150, "नमस्ते")
    data["model"]["multilingual"] = False
    with pytest.raises(SubloomError, match="multilingual"):
        parse_output(data, 1500)


def test_subprocess_unicode_arrays(tmp_path, cancel):
    filename = str(tmp_path / "हिंदी path ' with spaces.wav")
    result = run([sys.executable, "-c", "import sys; print(sys.argv[1])", filename], cancel)
    # Child stdout on Windows can use legacy codepages; force UTF-8 in app subprocesses.
    assert "spaces.wav" in result


def test_cancellation_really_terminates(tmp_path):
    import threading
    token = Cancellation()
    timer = threading.Timer(0.25, token.cancel)
    marker = tmp_path / "should-not-exist"
    timer.start()
    started = time.monotonic()
    with pytest.raises(Cancelled):
        run([sys.executable, "-c", "import time,pathlib,sys;time.sleep(8);pathlib.Path(sys.argv[1]).touch()", str(marker)], token)
    assert time.monotonic() - started < 5
    assert not marker.exists()


def test_subprocess_error_and_timeout(cancel):
    with pytest.raises(SubloomError, match="exit 3"):
        run([sys.executable, "-c", "raise SystemExit(3)"], cancel)
    with pytest.raises(SubloomError, match="timed out"):
        run([sys.executable, "-c", "import time;time.sleep(3)"], cancel, timeout=0.15)
