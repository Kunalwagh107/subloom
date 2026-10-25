"""Full actual CPU workflow through the same controller used by QML."""
import hashlib

import pytest

from subloom.media import probe
from subloom.process import Cancellation, run
from subloom.ui.bridge import Controller


@pytest.mark.asr
@pytest.mark.gui
def test_actual_ui_pipeline_edit_all_exports(qtbot, tmp_path, ffmpeg, model_dir, monkeypatch, speech_corpus, request):
    from subloom.models import ModelManager
    if not ModelManager(model_dir).installed("base"):
        pytest.skip("The full controller smoke test requires the local multilingual Base model")
    speech = speech_corpus / "english.wav"
    if not speech.exists():
        pytest.skip("Generate local speech fixtures first")
    path = tmp_path / "recording हिन्दी.mp4"
    run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=s=640x360:r=24:d=8", "-i", str(speech),
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)], Cancellation())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    controller = Controller(tmp_path / "app")
    request.addfinalizer(controller.shutdown)
    errors = []
    controller.alert.connect(errors.append)
    controller.import_path(str(path))
    qtbot.waitUntil(lambda: controller.job is None, timeout=15000)
    controller.options["model_dir"] = str(model_dir)
    for key, value in {"model": "base", "profile": "Eco", "device": "CPU", "language": "en"}.items():
        controller.setOption(key, value)
    controller.generate()
    qtbot.waitUntil(lambda: controller.job is None, timeout=120000)
    assert not errors and controller.captions.items
    assert "neural" in " ".join(s.text.lower() for s in controller.captions.items)
    first = controller.captions.items[0]
    from subloom.subtitles import timestamp
    controller.editCue(first.id, timestamp(first.start_ms, "."), timestamp(first.end_ms, "."), "Manually corrected captions")
    assert controller.session.raw[0].text != "Manually corrected captions"
    # Use the actual UI export handler with a deterministic destination picker.
    for fmt in ("srt", "vtt", "txt", "mp4"):
        destination = tmp_path / f"edited.{fmt}"
        monkeypatch.setattr("subloom.ui.bridge.QFileDialog.getSaveFileName", lambda *_a, dest=destination, **_k: (str(dest), ""))
        controller.export(fmt, True)
        qtbot.waitUntil(lambda: controller.job is None, timeout=30000)
        assert destination.exists() and destination.stat().st_size > 0
        if fmt != "mp4":
            assert "Manually corrected captions" in destination.read_text(encoding="utf-8")
        else:
            exported = probe(destination, Cancellation())
            assert (exported.width, exported.height, exported.frame_rate) == (640, 360, "24/1")
            assert exported.audio_tracks
    controller.setOption("mode", "english")
    controller.generate()
    qtbot.waitUntil(lambda: controller.job is None, timeout=120000)
    assert "english" in controller.session.generated
    controller.setOption("mode", "hinglish")
    assert controller.captions.items[0].text == "Manually corrected captions"
    assert not errors
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
