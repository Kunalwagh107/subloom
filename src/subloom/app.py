import os
import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QLockFile, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMessageBox

from .ui.bridge import Controller
from .paths import data_dir
from . import __version__


def create_application():
    os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")
    # Do not enable additional network protocols for Qt's FFmpeg backend.
    os.environ.setdefault("QT_FFMPEG_PROTOCOL_WHITELIST", "file,pipe")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("Subloom")
    app.setApplicationName("Subloom")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "ui" / "icon.svg")))
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in {QPalette.Window: "#0c1018", QPalette.WindowText: "#edf2ff",
                        QPalette.Base: "#121a27", QPalette.AlternateBase: "#1a2435",
                        QPalette.Text: "#edf2ff", QPalette.Button: "#26344b", QPalette.ButtonText: "#edf2ff",
                        QPalette.Highlight: "#7796ff", QPalette.HighlightedText: "#091329",
                        QPalette.ToolTipBase: "#202c40", QPalette.ToolTipText: "#edf2ff",
                        QPalette.PlaceholderText: "#91a0b8", QPalette.Light: "#35445e",
                        QPalette.Mid: "#26344b", QPalette.Dark: "#080b12"}.items():
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#68768e"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#68768e"))
    app.setPalette(palette)
    # Qt's offscreen Windows plugin does not enumerate system fonts itself.
    if os.name == "nt" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        for name in ("segoeui.ttf", "seguisb.ttf", "consola.ttf", "Nirmala.ttc", "Nirmala.ttf", "seguisym.ttf"):
            font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
            if font.exists():
                QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Segoe UI", 10))
    QQuickStyle.setStyle("Basic")
    controller = Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "ui" / "Main.qml")))
    return app, engine, controller


def main():
    parser = argparse.ArgumentParser(description="Subloom — local desktop subtitles")
    parser.add_argument("--smoke-test", type=Path, help="Write a local package diagnostic JSON and exit")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    lock = QLockFile(str(data_dir() / "application.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        QMessageBox.information(None, "Subloom is already open", "Use the existing Subloom window. One inference job runs at a time.")
        return
    app, engine, controller = create_application()
    if not engine.rootObjects():
        raise SystemExit("Subloom could not load its interface.")
    app.aboutToQuit.connect(controller.shutdown)
    if args.smoke_test:
        def smoke():
            from .media import executable
            from .process import Cancellation, run
            from .session import atomic_json
            try:
                runtime = {}
                for name in ("ffmpeg", "ffprobe", "whisper-cli"):
                    output = run([executable(name), "--help" if name == "whisper-cli" else "-version"],
                                 Cancellation(), timeout=15)
                    runtime[name] = next((line for line in output.splitlines() if line.strip()), "")
                from .whisper_engine import WhisperEngine
                gpu = WhisperEngine.gpu_cli()
                if gpu:
                    WhisperEngine.validate_cli(str(gpu), Cancellation())
                atomic_json(args.smoke_test, {"qml_loaded": bool(engine.rootObjects()), "runtime": runtime,
                                             "version": __version__, "frozen": bool(getattr(sys, "frozen", False)),
                                             "gpu_runtime_detected": gpu is not None})
                engine.rootObjects()[0].grabWindow().save(str(args.smoke_test.with_suffix(".png")))
            finally:
                app.quit()
        QTimer.singleShot(500, smoke)
    exit_code = app.exec()
    # Destroy QML bindings while their Python context objects are still alive.
    for window in engine.rootObjects():
        window.close()
    engine.deleteLater()
    app.sendPostedEvents()
    sys.exit(exit_code)
