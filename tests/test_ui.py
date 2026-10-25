import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtMultimedia import QMediaPlayer
import pytest

from subloom.process import Cancellation
from subloom.session import Session, cache_key
from subloom.subtitles import segment
from subloom.ui.bridge import CaptionModel, Controller
from test_media import make_media

pytestmark = pytest.mark.gui


def wait_idle(qtbot, controller):
    qtbot.waitUntil(lambda: controller.job is None, timeout=15000)


def test_caption_index_overlaps_and_updates(qapp):
    model = CaptionModel()
    first = segment(0, 10000, "long")
    second = segment(1000, 2000, "short")
    model.set_items([first, second])
    assert model.at(1500) == "long\nshort"
    assert model.at(2500) == "long"
    model.update(replace(first, end_ms=1500))
    assert model.at(2500) == ""
    assert model.rowCount() == 2


@pytest.mark.gui
def test_repeated_worker_completion_joins_before_disposal(qtbot, tmp_path):
    controller = Controller(tmp_path / "app")
    results = []
    for i in range(35):
        controller._start(lambda _c, _p, value=i: value, results.append, "Checking worker disposal")
        wait_idle(qtbot, controller)
    assert results == list(range(35))
    controller.shutdown()


@pytest.mark.gui
def test_cancelled_translation_restores_raw_without_misattributing_edits(qtbot, tmp_path):
    from subloom.errors import Cancelled
    from subloom.session import atomic_json
    controller = Controller(tmp_path / "app")
    controller.source = {"sha256": "test-only-source"}
    raw = segment(0, 900, "Completed raw ASR")
    completed = Session(controller.source, 1000, "base", {}, "test-key", raw=[raw],
                        generated={"original": [raw]}, mode="english")
    def cancelled_translation(_cancel, _progress):
        atomic_json(controller.session_path, completed.to_dict())
        raise Cancelled("Translation cancelled after raw ASR completed")
    controller._start(cancelled_translation, lambda _: None, "Translating")
    wait_idle(qtbot, controller)
    assert controller.session.mode == "original"
    assert controller.captions.items == [raw]
    assert "english" not in controller.session.edits
    controller.shutdown()


@pytest.mark.gui
def test_playback_seek_real_frames_and_responsive_worker(qtbot, tmp_path, ffmpeg):
    cancel = Cancellation()
    path = make_media(ffmpeg, tmp_path / "playback.mp4", cancel, extra_audio=True)
    controller = Controller(tmp_path / "app")
    errors = []
    controller.alert.connect(errors.append)
    controller.import_path(str(path))
    wait_idle(qtbot, controller)
    assert controller.state["hasMedia"] and controller.state["hasVideo"]
    assert not errors
    from PySide6.QtMultimedia import QVideoSink
    sink = QVideoSink()
    frames = []
    sink.videoFrameChanged.connect(lambda frame: frames.append(frame.isValid()))
    controller.attachVideo(sink)
    qtbot.waitUntil(lambda: controller.player.mediaStatus() in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia), timeout=10000)
    assert controller.player.activeAudioTrack() == 1
    controller.setOption("track", controller.media.audio_tracks[0].index)
    qtbot.waitUntil(lambda: controller.player.activeAudioTrack() == 0, timeout=3000)
    controller.togglePlayback()
    qtbot.waitUntil(lambda: controller.player.position() >= 200, timeout=10000)
    assert any(frames)
    controller.togglePlayback()
    controller.seek(1000)
    qtbot.waitUntil(lambda: controller.player.position() >= 950, timeout=3000)
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(15)
    def work(token, progress):
        while True:
            token.check()
            time.sleep(0.02)
    controller._start(work, lambda _: None, "Testing cancellation")
    qtbot.wait(220)
    assert len(ticks) >= 5
    controller.cancel()
    wait_idle(qtbot, controller)
    assert not controller.state["busy"]
    timer.stop()
    controller.shutdown()


@pytest.mark.gui
def test_edit_autosave_restart_and_selected_mode(qtbot, tmp_path, ffmpeg):
    path = make_media(ffmpeg, tmp_path / "source.wav", Cancellation(), video=False)
    controller = Controller(tmp_path / "app")
    controller.import_path(str(path))
    wait_idle(qtbot, controller)
    settings = controller._settings()
    from subloom.models import MODELS
    key = cache_key(controller.source, controller.options["model"], MODELS[controller.options["model"]].sha256, settings)
    raw = segment(0, 1000, "आज neural networks")
    session = Session(controller.source, controller.media.duration_ms, controller.options["model"], settings, key,
                      raw=[raw], generated={"original": [raw], "hinglish": [replace(raw, text="aaj neural networks")]})
    controller.session = session
    controller.captions.set_items(session.captions("hinglish"))
    controller.editCue(raw.id, "00:00:00.050", "00:00:01.100", "Edited English API")
    assert controller.captionAt(100) == "Edited English API"
    assert session.raw[0].text == "आज neural networks"
    controller.setOption("mode", "original")
    assert controller.captionAt(100) == "आज neural networks"
    controller.setOption("mode", "hinglish")
    assert controller.captionAt(100) == "Edited English API"
    controller.addCue()
    assert controller.captions.rowCount() == 2
    controller.removeCue(next(s.id for s in controller.captions.items if s.id != raw.id))
    assert controller.captions.rowCount() == 1
    controller.shutdown()
    recovered = Controller(tmp_path / "app")
    qtbot.waitUntil(lambda: recovered.media is not None and recovered.job is None, timeout=15000)
    assert recovered.session.raw[0].text == "आज neural networks"
    assert recovered.captions.items[0].text == "Edited English API"
    recovered.shutdown()


def test_restart_keeps_new_speed_settings_over_old_caption_settings(qtbot, tmp_path, ffmpeg):
    source = make_media(ffmpeg, tmp_path / "resume.wav", Cancellation(), video=False)
    controller = Controller(tmp_path / "app")
    controller.import_path(str(source))
    wait_idle(qtbot, controller)
    controller.session = Session(controller.source, controller.media.duration_ms, "base",
                                 {"track": controller.media.default_track, "profile": "Eco", "device": "CPU", "language": "en"},
                                 "older-result", raw=[segment(0, 900, "saved result")],
                                 generated={"original": [segment(0, 900, "saved result")]}, mode="original")
    controller.setOption("model", "small")
    controller.setOption("profile", "Performance")
    controller.setOption("decoding", "fast")
    controller.shutdown()
    resumed = Controller(tmp_path / "app")
    qtbot.waitUntil(lambda: resumed.media is not None and resumed.job is None, timeout=15000)
    assert resumed.options["model"] == "small"
    assert resumed.options["profile"] == "Performance"
    assert resumed.options["decoding"] == "fast"
    assert resumed.session.model_id == "base"  # Original provenance never rewritten.
    resumed.shutdown()


@pytest.mark.gui
def test_qml_loads_and_resizes(qapp, qtbot, tmp_path, monkeypatch, ffmpeg):
    monkeypatch.setenv("SUBLOOM_DATA_DIR", str(tmp_path))
    from subloom.app import create_application
    app, engine, controller = create_application()
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    window.setWidth(1000)
    window.setHeight(720)
    qtbot.wait(150)
    assert window.findChild(CaptionModel) is None  # Model is exposed through controller, not copied per frame.
    Path(".test-data").mkdir(exist_ok=True)
    assert window.grabWindow().save(".test-data/ui-test.png")
    from PySide6.QtCore import QObject, QMetaObject
    choice = window.findChild(QObject, "modeChoice")
    popup = choice.findChild(QObject, "darkChoicePopup")
    QMetaObject.invokeMethod(popup, "open")
    qtbot.wait(100)
    assert popup.property("visible")
    assert popup.findChild(QObject, "darkChoiceBackground").property("color").name() == "#162136"
    assert window.grabWindow().save(".test-data/dark-options-test.png")
    QMetaObject.invokeMethod(popup, "close")
    settings = window.findChild(QObject, "settingsDialog")
    QMetaObject.invokeMethod(settings, "open")
    qtbot.wait(100)
    assert window.grabWindow().save(".test-data/dark-settings-test.png")
    QMetaObject.invokeMethod(settings, "close")
    help_dialog = window.findChild(QObject, "helpDialog")
    QMetaObject.invokeMethod(help_dialog, "open")
    qtbot.wait(80)
    assert help_dialog.property("visible")
    from subloom import __version__
    assert controller.state["version"] == __version__
    QMetaObject.invokeMethod(help_dialog, "close")
    source = make_media(ffmpeg, tmp_path / "qml.wav", Cancellation(), video=False)
    controller.import_path(str(source))
    wait_idle(qtbot, controller)
    controller.captions.set_items([segment(0, 1200, "आज हम neural networks समझेंगे।"),
                                 segment(1300, 1900, "Editable English / हिन्दी captions")])
    controller.changed.emit()
    qtbot.wait(250)
    assert window.grabWindow().save(".test-data/editor-test.png")
    window.setWidth(960)
    window.setHeight(540)  # Typical 1080p desktop at 200% scaling, in logical pixels.
    qtbot.wait(100)
    from PySide6.QtCore import QObject
    workspace = window.findChild(QObject, "workspace")
    assert workspace.property("contentHeight") > workspace.property("height")
    assert window.grabWindow().save(".test-data/compact-test.png")
    window.close()
    controller.shutdown()
    engine.deleteLater()
