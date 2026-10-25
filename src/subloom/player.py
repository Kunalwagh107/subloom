from pathlib import Path
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class Player(QObject):
    error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.media = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.85)
        self.media.setAudioOutput(self.audio)
        self._audio_track = 0
        self.media.tracksChanged.connect(self._apply_track)
        self.media.errorOccurred.connect(lambda _code, message: self.error.emit(
            f"Playback failed: {message}. FFmpeg transcription may still work; check the Qt Multimedia codecs."))

    def open(self, path: Path, audio_track: int = 0) -> None:
        self.media.stop()
        self._audio_track = audio_track
        self.media.setSource(QUrl.fromLocalFile(str(path.resolve())))

    def select_track(self, ordinal: int) -> None:
        self._audio_track = ordinal
        self._apply_track()

    def _apply_track(self) -> None:
        if 0 <= self._audio_track < len(self.media.audioTracks()):
            self.media.setActiveAudioTrack(self._audio_track)

    @Slot()
    def toggle(self) -> None:
        if self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media.pause()
        else:
            self.media.play()
