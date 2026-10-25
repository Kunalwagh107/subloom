"""Capture public documentation using synthetic speech and real local CPU inference.

No downloads or user profile access. This is developer tooling, not app functionality.
Requires an explicitly supplied Base model and the generated English fixture.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from PySide6.QtCore import QObject, QMetaObject, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer

from subloom.media import executable
from subloom.process import Cancellation, run
from subloom.session import atomic_json
from subloom.subtitles import timestamp


def render_svg(source: Path, destination: Path, width: int, height: int) -> None:
    canvas = QImage(width, height, QImage.Format_ARGB32)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    QSvgRenderer(str(source)).render(painter)
    painter.end()
    assert canvas.save(str(destination))


def sample_picture(destination: Path) -> None:
    image = QImage(1280, 720, QImage.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, 1280, 720)
    gradient.setColorAt(0, QColor("#152741"))
    gradient.setColorAt(1, QColor("#090f1a"))
    painter.fillRect(image.rect(), gradient)
    painter.setPen(QColor("#91a8d8"))
    painter.setFont(QFont("Segoe UI", 17))
    painter.drawText(76, 82, "TECH NOTES / 01")
    painter.setPen(QColor("#f0f3ff"))
    painter.setFont(QFont("Segoe UI", 42, QFont.DemiBold))
    painter.drawText(76, 166, "Learning neural networks")
    painter.setPen(QColor("#adbedb"))
    painter.setFont(QFont("Segoe UI", 20))
    painter.drawText(78, 218, "A short, locally generated sample recording")
    nodes = [(160, 365), (160, 485), (430, 345), (430, 425), (430, 505), (700, 425)]
    painter.setPen(QPen(QColor("#3c5382"), 3))
    for a, b in ((0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (1, 4), (2, 5), (3, 5), (4, 5)):
        painter.drawLine(*nodes[a], *nodes[b])
    for x, y in nodes:
        painter.setPen(QPen(QColor("#b3c0ff"), 3))
        painter.setBrush(QColor("#253756"))
        painter.drawEllipse(QRectF(x - 20, y - 20, 40, 40))
    painter.setPen(QColor("#91a8d8"))
    painter.setFont(QFont("Segoe UI", 15))
    painter.drawText(870, 421, "HELLO, SUBTITLES.")
    painter.drawText(870, 456, "No camera footage.")
    painter.drawText(870, 488, "No personal data.")
    painter.end()
    assert image.save(str(destination))


def capture(work: Path, output: Path, model_dir: Path, speech: Path) -> None:
    from subloom.app import create_application
    from subloom.ui.bridge import QFileDialog

    (work / "models").mkdir()
    for name in ("ggml-base.bin", "ggml-small.bin"):
        source = model_dir / name
        if source.is_file():
            try:
                os.link(source, work / "models" / name)
            except OSError:
                shutil.copy2(source, work / "models" / name)
    os.environ["SUBLOOM_DATA_DIR"] = str(work / "profile")
    # Exercise the CPU-only installation path; do not load the optional CUDA build.
    os.environ["SUBLOOM_GPU_CLI"] = str(work / "not-installed" / "whisper-cli.exe")
    atomic_json(work / "profile" / "settings.json", {"device": "CPU", "model": "base", "profile": "Eco",
                "language": "en", "mode": "original", "model_dir": "models"})
    previous_cwd = Path.cwd()
    os.chdir(work)
    app, engine, controller = create_application()
    window = engine.rootObjects()[0]
    window.setWidth(1360)
    window.setHeight(900)
    controller.playback.audio.setVolume(0)
    errors = []
    controller.alert.connect(errors.append)
    ffmpeg = executable("ffmpeg")
    recorder = None
    picker = QFileDialog.getSaveFileName
    try:
        root = Path(__file__).resolve().parents[1]
        shutil.copy2(root / "src/subloom/ui/icon.svg", output / "subloom-logo.svg")
        banner = root / "docs/assets/subloom-banner.svg"
        if banner.resolve() != (output / banner.name).resolve():
            shutil.copy2(banner, output / banner.name)
        render_svg(output / "subloom-logo.svg", output / "subloom-logo.png", 320, 320)
        render_svg(output / "subloom-banner.svg", output / "subloom-banner.png", 1280, 336)
        sample_picture(work / "lesson.png")
        run([ffmpeg, "-v", "error", "-loop", "1", "-i", "lesson.png", "-i", str(speech),
             "-c:v", "libx264", "-tune", "stillimage", "-r", "24", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", "Neural networks - demo.mp4"], Cancellation())
        for _ in range(30):
            app.processEvents()
            time.sleep(0.02)
        recorder = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "1360x900", "-r", "8", "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output / "subloom-demo.mp4")],
            stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        next_frame = time.monotonic()

        def pump():
            nonlocal next_frame
            app.processEvents()
            now = time.monotonic()
            if now >= next_frame:
                frame = window.grabWindow().convertToFormat(QImage.Format_RGB888)
                if frame.width() != 1360 or frame.height() != 900:
                    raise RuntimeError("Unexpected capture dimensions")
                recorder.stdin.write(bytes(frame.constBits()))
                next_frame += 1 / 8
            time.sleep(0.004)

        def wait(seconds):
            until = time.monotonic() + seconds
            while time.monotonic() < until:
                pump()

        def idle(timeout=180):
            until = time.monotonic() + timeout
            while controller.job is not None:
                if time.monotonic() > until:
                    raise RuntimeError("Real demo job timed out")
                pump()
            if errors:
                raise RuntimeError("Demo operation failed: " + errors[-1])

        wait(1)
        assert window.grabWindow().save(str(output / "welcome.png"))
        settings = window.findChild(QObject, "settingsDialog")
        QMetaObject.invokeMethod(settings, "open")
        wait(1.5)
        assert window.grabWindow().save(str(output / "models.png"))
        QMetaObject.invokeMethod(settings, "close")
        wait(0.5)
        controller.import_path(str(work / "Neural networks - demo.mp4"))
        idle(20)
        wait(1)
        controller.generate()
        idle()
        assert controller.session.raw and controller.captions.items
        wait(1)
        # Review the actual recognition using the known synthetic reference.
        # These are explicit editor corrections, never a substitute ASR result.
        for item in list(controller.captions.items):
            controller.removeCue(item.id)
        for start, end, text in [(0, 1300, "Hello everyone."), (1300, 4800, "Today we will learn about neural networks."),
                                 (4800, controller.media.duration_ms, "This recording stays on this computer.")]:
            previous = {s.id for s in controller.captions.items}
            controller.addCue()
            item = next(s for s in controller.captions.items if s.id not in previous)
            controller.editCue(item.id, timestamp(start, "."), timestamp(end, "."), text)
            wait(0.8)
        controller.seek(1800)
        controller.togglePlayback()
        wait(1)
        controller.togglePlayback()
        wait(0.5)
        assert window.grabWindow().save(str(output / "editor.png"))
        controller.seek(0)
        controller.togglePlayback()
        wait(7.8)
        for fmt in ("srt", "mp4"):
            QFileDialog.getSaveFileName = lambda *_a, extension=fmt, **_k: (f"Demo captions.{extension}", "")
            controller.export(fmt, True)
            idle(60)
            assert (work / f"Demo captions.{fmt}").is_file()
            wait(1)
        recorder.stdin.close()
        if recorder.wait(timeout=30):
            raise RuntimeError("Demo encoding failed")
        recorder = None
    finally:
        QFileDialog.getSaveFileName = picker
        controller.shutdown()
        window.close()
        engine.deleteLater()
        app.sendPostedEvents()
        if recorder is not None:
            recorder.stdin.close()
            recorder.wait(timeout=30)
        os.chdir(previous_cwd)
    run([ffmpeg, "-v", "error", "-y", "-i", str(output / "subloom-demo.mp4"), "-vf",
         "fps=5,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
         "-loop", "0", str(output / "subloom-demo.gif")], Cancellation())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--speech", type=Path, required=True, help="Generated english.wav from make_speech_fixtures.py")
    parser.add_argument("--output", type=Path, default=Path("docs/assets"))
    args = parser.parse_args()
    model_dir, speech, output = args.model_dir.resolve(), args.speech.resolve(), args.output.resolve()
    if not (model_dir / "ggml-base.bin").is_file() or not speech.is_file():
        parser.error("Supply an installed multilingual Base model and the generated English fixture.")
    output.mkdir(parents=True, exist_ok=True)
    # Native capture + CPU video decoding avoids hybrid-GPU texture readback
    # problems. This affects this capture process only, not application defaults.
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")
    os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", ",")
    os.environ.setdefault("QT_DISABLE_HW_TEXTURES_CONVERSION", "1")
    os.environ.setdefault("QSG_RHI_BACKEND", "opengl")
    cache = Path(__file__).resolve().parents[1] / ".test-data"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="public-visuals-", dir=cache) as temporary:
        capture(Path(temporary), output, model_dir, speech)
    print(f"Public screenshots and silent demo saved to {output}")


if __name__ == "__main__":
    main()
