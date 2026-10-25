from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import time

from PySide6.QtCore import (QAbstractListModel, QModelIndex, QObject, Property, Qt, QTimer,
                            QUrl, Signal, Slot)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from subloom.errors import SubloomError
from subloom import __version__
from subloom.hardware import compatibility, detect
from subloom.language import script_warning
from subloom.media import burn_video, probe
from subloom.models import MODELS, ModelManager
from subloom.paths import data_dir
from subloom.pipeline import generate
from subloom.player import Player
from subloom.session import Session, atomic_json, cache_key, identity, load_session, load_settings
from subloom.subtitles import SubtitleSegment, export_text, parse_time, segment, timestamp
from subloom.whisper_engine import WhisperEngine
from subloom.workers import Job
from subloom.runtime import install_gpu


class CaptionModel(QAbstractListModel):
    ROLES = {Qt.UserRole + 1: b"cueId", Qt.UserRole + 2: b"startTime", Qt.UserRole + 3: b"endTime",
             Qt.UserRole + 4: b"captionText"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[SubtitleSegment] = []
        self.starts: list[int] = []
        self.max_ends: list[int] = []

    def roleNames(self):
        return self.ROLES

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.items):
            return None
        s = self.items[index.row()]
        return {Qt.UserRole + 1: s.id, Qt.UserRole + 2: timestamp(s.start_ms, "."),
                Qt.UserRole + 3: timestamp(s.end_ms, "."), Qt.UserRole + 4: s.text}.get(role)

    def set_items(self, items):
        self.beginResetModel()
        self.items = sorted(items, key=lambda s: (s.start_ms, s.end_ms))
        self.starts = [s.start_ms for s in self.items]
        maximum = 0
        self.max_ends = []
        for s in self.items:
            maximum = max(maximum, s.end_ms)
            self.max_ends.append(maximum)
        self.endResetModel()

    def update(self, item):
        index = next(i for i, s in enumerate(self.items) if s.id == item.id)
        old = self.items[index]
        if item.start_ms == old.start_ms and item.end_ms == old.end_ms:
            self.items[index] = item
            self.dataChanged.emit(self.index(index), self.index(index), list(self.ROLES))
        else:
            self.set_items([item if s.id == item.id else s for s in self.items])

    def at(self, position: int) -> str:
        index = bisect_right(self.starts, position)
        # Simultaneous captions are legal: concatenate active cues, no list resets per frame.
        result = []
        for i in range(index - 1, -1, -1):
            if self.max_ends[i] <= position:
                break
            item = self.items[i]
            if item.start_ms <= position < item.end_ms:
                result.append(item.text)
        return "\n".join(reversed(result))


class Controller(QObject):
    changed = Signal()
    alert = Signal(str)
    gpuRetry = Signal(str)
    saveFailed = Signal(str)

    def __init__(self, root: Path | None = None):
        super().__init__()
        self.root = (root or data_dir()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.session_path = self.root / "current.session.json"
        self.settings_path = self.root / "settings.json"
        saved = load_settings(self.settings_path)
        self.last_opened_path = saved.get("last_file", "")
        hardware = detect()
        self.options = {"model": "small" if hardware.available_gb >= 3 else "base", "mode": "hinglish",
                        "profile": "Balanced", "device": "Auto", "language": "auto", "track": 0,
                        "decoding": "standard",
                        "model_dir": str(self.root / "models")}
        self.options.update({k: v for k, v in saved.items() if k in self.options})
        for field, allowed in {"model": MODELS, "mode": {"hinglish", "english", "original"},
                               "profile": {"Eco", "Balanced", "Performance"}, "device": {"Auto", "CPU", "GPU"},
                               "language": {"auto", "hi", "en"}, "decoding": {"standard", "fast"}}.items():
            if self.options[field] not in allowed:
                self.options[field] = next(iter(allowed))
        self.media = None
        self.source = None
        self.session: Session | None = None
        self.captions = CaptionModel(self)
        self.playback = Player(self)
        self.playback.error.connect(self.alert)
        self.job: Job | None = None
        self._state = {"busy": False, "step": "Ready when you are", "progress": -1.0, "elapsed": 0,
                       "output": "", "modelStatus": "", "notice": "", "error": ""}
        self._save_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="subloom-save")
        self._last_save = None
        self.saveFailed.connect(self.alert)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(350)
        self.save_timer.timeout.connect(self._save)
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._tick)
        self.started = 0.0
        if saved.get("last_file") and Path(saved["last_file"]).is_file():
            QTimer.singleShot(0, lambda: self.import_path(saved["last_file"]))

    @Property(QObject, constant=True)
    def captionModel(self):
        return self.captions

    @Property(QObject, constant=True)
    def player(self):
        return self.playback.media

    @Property("QVariantMap", notify=changed)
    def state(self):
        manager = ModelManager(Path(self.options["model_dir"]))
        hardware = detect()
        models = []
        for key, model in MODELS.items():
            status, reason = compatibility(key, hardware)
            models.append({"id": key, "name": model.name, "bytes": model.bytes, "description": model.description,
                           "compatibility": status, "reason": reason, "installed": manager.installed(key)})
        media = self.media
        return {**self._state, **self.options, "version": __version__, "hasMedia": media is not None,
                "filename": Path(media.path).name if media else "", "path": media.path if media else "",
                "duration": media.duration_ms if media else 0,
                "mediaType": "Video" if media and media.video_index is not None else "Audio",
                "hasVideo": bool(media and media.video_index is not None),
                "tracks": [{"index": t.index, "label": t.label} for t in media.audio_tracks] if media else [],
                "models": models, "count": self.captions.rowCount(),
                "modelReady": manager.installed(self.options["model"]),
                "hardware": f"{hardware.cpus} CPU threads · {hardware.ram_gb:.0f} GB RAM · {hardware.available_gb:.1f} GB available",
                "gpuAvailable": bool(hardware.gpu_name) and WhisperEngine.gpu_cli() is not None,
                "gpuName": hardware.gpu_name,
                "gpuReason": (f"{hardware.gpu_name} · {hardware.vram_mb / 1024:.0f} GB VRAM · Auto accelerates Balanced and Performance."
                              if hardware.gpu_name and WhisperEngine.gpu_cli() else
                              "NVIDIA GPU detected; install the GPU-enabled build to accelerate inference." if hardware.gpu_name else
                              "CPU processing available. A compatible NVIDIA GPU is optional."),
                "longRecording": bool(media and media.duration_ms >= 3600000),
                "captionMode": self.session.mode if self.session else "", "saved": self.session is not None,
                "notice": (script_warning(self.session.raw) if self.session and self.session.mode == "hinglish" else "") or self._state["notice"]}

    def _notify(self, **values):
        self._state.update(values)
        self.changed.emit()

    def _tick(self):
        self._notify(elapsed=int(time.monotonic() - self.started))

    def _settings(self) -> dict:
        settings = {key: self.options[key] for key in ("track", "profile", "device", "language")}
        if self.options["decoding"] == "fast":
            settings["decoding"] = "fast"
        return settings

    def _key(self) -> str:
        return cache_key(self.source, self.options["model"], MODELS[self.options["model"]].sha256, self._settings())

    def _save(self):
        settings = dict(self.options)
        if self.media:
            settings["last_file"] = self.media.path
        snapshot = self.session.to_dict() if self.session else None

        def write():
            try:
                atomic_json(self.settings_path, settings)
                if snapshot:
                    atomic_json(self.session_path, snapshot)
            except OSError as exc:
                self.saveFailed.emit(f"Autosave failed. Check disk space and permissions: {exc}")

        self._last_save = self._save_pool.submit(write)

    def _flush(self):
        self.save_timer.stop()
        self._save()
        if self._last_save:
            self._last_save.result()

    def _start(self, function, success, step):
        if self.job is not None:
            return
        self._flush()
        self.started = time.monotonic()
        self._notify(busy=True, step=step, progress=-1.0, elapsed=0, error="")
        job = Job(function, self)
        self.job = job
        job.progress.connect(lambda text, value: self._notify(step=text, progress=-1.0 if value is None else float(value)))
        job.succeeded.connect(success)
        job.failed.connect(self._failed)
        job.finished.connect(self._finished)
        self.elapsed_timer.start()
        job.start()

    def _failed(self, kind, text):
        self._notify(step="Cancelled" if kind == "cancel" else "Needs attention", error="" if kind == "cancel" else text,
                     modelStatus="Cancelled" if kind == "cancel" else "Failed")
        # An initial ASR pass may have completed before a cancelled translation.
        try:
            recovered = load_session(self.session_path)
            if recovered and self.source and recovered.source == self.source:
                if recovered.mode not in recovered.generated:
                    recovered.mode = "original" if "original" in recovered.generated else next(iter(recovered.generated), recovered.mode)
                self.session = recovered
                self.captions.set_items(recovered.captions(recovered.mode))
                self._notify(notice="Recovered completed captions. The requested operation did not finish.")
        except SubloomError:
            pass
        if kind == "gpu":
            self.gpuRetry.emit(text)
        elif kind != "cancel":
            self.alert.emit(text)

    def _finished(self):
        job = self.job
        if job:
            # QThread.finished is emitted before native thread-local cleanup.
            # Join before allowing the next job or deleting its owning QObject.
            job.wait()
        self.job = None
        self.elapsed_timer.stop()
        self._notify(busy=False, progress=-1.0)
        if job:
            job.deleteLater()

    @Slot(str)
    def importUrl(self, url):
        parsed = QUrl(url)
        if parsed.isLocalFile():
            self.import_path(parsed.toLocalFile())
        else:
            self.alert.emit("Choose a file stored on this computer. Online media URLs are unsupported.")

    @Slot()
    def openFile(self):
        if self.job:
            return
        name, _ = QFileDialog.getOpenFileName(None, "Open video or audio", "", "Media (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus);;All files (*)")
        if name:
            self.import_path(name)

    def import_path(self, name: str):
        if self.job:
            return
        def work(cancel, progress):
            progress("Inspecting media with FFprobe", None)
            media = probe(Path(name), cancel)
            progress("Identifying recording for safe session recovery", None)
            source = identity(Path(media.path), cancel)
            restored = load_session(self.session_path)
            return media, source, restored

        def success(result):
            media, source, restored = result
            self.media, self.source = media, source
            preferred_track = self.options["track"]
            self.options["track"] = (preferred_track if self.last_opened_path == media.path and
                                     preferred_track in {t.index for t in media.audio_tracks} else media.default_track)
            self.session = None
            self.captions.set_items([])
            if restored and restored.source == source:
                self.session = restored
                self.captions.set_items(restored.captions(restored.mode))
            ordinal = next(i for i, t in enumerate(media.audio_tracks) if t.index == self.options["track"])
            self.playback.open(Path(media.path), ordinal)
            self.last_opened_path = media.path
            self._notify(step="Recording ready", notice="Saved captions recovered · Generate uses the selected settings" if self.session else "", output="")
            self.save_timer.start()
        self._start(work, success, "Opening recording")

    @Slot(str, "QVariant")
    def setOption(self, key, value):
        if self.job:
            return
        allowed = {"model": MODELS, "mode": {"hinglish", "english", "original"}, "profile": {"Eco", "Balanced", "Performance"},
                   "device": {"Auto", "CPU", "GPU"}, "language": {"auto", "en", "hi"}, "decoding": {"standard", "fast"}}
        if key == "track":
            if not self.media or int(value) not in {t.index for t in self.media.audio_tracks}:
                return
            value = int(value)
        elif key not in allowed or value not in allowed[key]:
            return
        self.options[key] = value
        if key == "track":
            ordinal = next(i for i, t in enumerate(self.media.audio_tracks) if t.index == value)
            self.playback.select_track(ordinal)
        if key == "mode" and self.session and self.session.key == self._key():
            if value in self.session.generated:
                self.session.mode = value
                self.captions.set_items(self.session.captions(value))
                self._state["notice"] = "Opened saved captions · no inference needed"
            else:
                self.captions.set_items([])
                self._state["notice"] = "Generate to create this output mode locally."
        elif self.session:
            self._state["notice"] = "Settings changed. Generate uses the new settings; existing captions remain saved."
        self.changed.emit()
        self.save_timer.start()

    @Slot()
    def generate(self):
        if not self.media or self.job:
            return
        manager = ModelManager(Path(self.options["model_dir"]))
        if not manager.installed(self.options["model"]):
            self.alert.emit("Download or import the selected model first. Downloads start only when you press Download.")
            return
        status, reason = compatibility(self.options["model"], detect())
        if status == "Not enough memory":
            self.alert.emit(reason + " Close other apps or explicitly select a smaller model.")
            return
        engine = WhisperEngine(manager, self.root / "cache", self.source, self.options["decoding"] == "fast")
        media, source, model_id, settings, mode = self.media, self.source, self.options["model"], self._settings(), self.options["mode"]
        previous = self.session

        def work(cancel, progress):
            return generate(media, source, model_id, settings, mode, previous, engine, self.session_path, cancel, progress)

        def success(session):
            self.session = session
            self.captions.set_items(session.captions(mode))
            warning = script_warning(session.raw) if mode == "hinglish" else ""
            self._notify(step="Captions ready", notice=warning or
                         f"Saved locally{(' · ' + engine.last_backend) if engine.last_backend else ''} · review captions before export")
            self.save_timer.start()
        self._start(work, success, "Starting local inference")

    @Slot()
    def retryCPU(self):
        self.setOption("device", "CPU")
        self.generate()

    @Slot()
    def cancel(self):
        if self.job:
            job = self.job
            job.cancel()
            self._notify(step="Cancelling safely…")

    @Slot()
    def downloadModel(self):
        if self.job:
            return
        manager = ModelManager(Path(self.options["model_dir"]))
        model_id = self.options["model"]
        self._notify(modelStatus="Downloading")
        def ready(_):
            self._notify(step="Model verified and ready", modelStatus="Ready")
        self._start(lambda c, p: manager.download(model_id, c, p), ready, "Downloading model")

    @Slot()
    def enableGPU(self):
        if self.job:
            return
        self._start(lambda c, p: install_gpu(self.root / "runtimes" / "gpu", c, p),
                    lambda _: self._notify(step="NVIDIA support installed", notice="Auto can now use the GPU with your selected model."),
                    "Installing optional NVIDIA acceleration")

    @Slot()
    def importModel(self):
        if self.job:
            return
        name, _ = QFileDialog.getOpenFileName(None, "Import verified multilingual GGML model", "", "GGML model (*.bin)")
        if name:
            manager = ModelManager(Path(self.options["model_dir"]))
            model_id = self.options["model"]
            self._start(lambda c, p: manager.import_model(model_id, Path(name), c, p),
                        lambda _: self._notify(step="Offline model verified and ready", modelStatus="Ready"), "Importing model")

    @Slot()
    def deleteModel(self):
        if self.job:
            return
        try:
            ModelManager(Path(self.options["model_dir"])).delete(self.options["model"])
            self._notify(modelStatus="Deleted", step="Model removed from this computer")
        except OSError as exc:
            self.alert.emit(f"Cannot delete model: {exc}")

    @Slot()
    def chooseModelFolder(self):
        if self.job:
            return
        folder = QFileDialog.getExistingDirectory(None, "Choose model folder", self.options["model_dir"])
        if folder:
            self.options["model_dir"] = folder
            self.changed.emit()
            self.save_timer.start()

    @Slot(QObject)
    def attachVideo(self, sink):
        self.playback.media.setVideoSink(sink)

    @Slot()
    def togglePlayback(self):
        self.playback.toggle()

    @Slot(int)
    def seek(self, position):
        self.playback.media.setPosition(position)

    @Slot(str)
    def seekCue(self, cue_id):
        item = next((s for s in self.captions.items if s.id == cue_id), None)
        if item:
            self.seek(item.start_ms)

    @Slot(int, result=str)
    def captionAt(self, position):
        return self.captions.at(position)

    @Slot(int, result=str)
    def formatTime(self, position):
        return timestamp(max(0, position), ".")

    def _edited(self):
        if self.session:
            self.session.edits[self.session.mode] = list(self.captions.items)
            self.save_timer.start()
        self.changed.emit()

    @Slot(str, str, str, str)
    def editCue(self, cue_id, start, end, text):
        if self.job or not self.media:
            return
        try:
            original = next(s for s in self.captions.items if s.id == cue_id)
            item = replace(original, start_ms=parse_time(start), end_ms=parse_time(end), text=text)
            item.validate(self.media.duration_ms)
            self.captions.update(item)
            self._edited()
        except (SubloomError, StopIteration) as exc:
            self.alert.emit(str(exc))

    @Slot()
    def addCue(self):
        if self.job or not self.media or not self.session:
            return
        start = min(self.playback.media.position(), self.media.duration_ms - 1)
        item = segment(start, min(start + 2000, self.media.duration_ms), "New caption")
        self.captions.set_items(self.captions.items + [item])
        self._edited()

    @Slot(str)
    def removeCue(self, cue_id):
        if not self.job:
            self.captions.set_items([s for s in self.captions.items if s.id != cue_id])
            self._edited()

    @Slot(str, bool)
    def export(self, fmt, timed_text=False):
        if self.job or not self.captions.items or not self.media:
            return
        if fmt not in {"srt", "vtt", "txt", "mp4"}:
            return
        name, _ = QFileDialog.getSaveFileName(None, "Export captions", str(Path(self.media.path).with_suffix("")) + f".subloom.{fmt}",
                                             f"{fmt.upper()} (*.{fmt})", options=QFileDialog.Option.DontConfirmOverwrite)
        if not name:
            return
        path = Path(name)
        if path.suffix.lower() != "." + fmt:
            path = Path(str(path) + "." + fmt)
        media, track, items = self.media, self.options["track"], list(self.captions.items)
        def work(cancel, progress):
            if fmt == "mp4":
                return burn_video(media, track, items, path, cancel, progress, self.root / "cache")
            export_text(items, path, fmt, Path(media.path), timed_text)
            return path
        self._start(work, lambda result: self._notify(output=str(result), step="Export complete"), "Exporting edited captions")

    @Slot()
    def revealOutput(self):
        if self._state["output"]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._state["output"]).parent)))

    def shutdown(self):
        if self.job:
            job = self.job
            job.cancel()
            while job.isRunning():
                job.wait(50)
            # Deliver completed raw-pass recovery/success before the final save.
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.processEvents()
        self.playback.media.stop()
        self.playback.media.setSource(QUrl())
        self._flush()
        self._save_pool.shutdown(wait=True)
