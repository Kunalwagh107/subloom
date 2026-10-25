import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shutil
import tempfile

from .errors import SubloomError
from .paths import tools_dir
from .process import Cancellation, Progress, run
from .subtitles import SubtitleSegment, ensure_new_destination, render


def executable(name: str) -> str:
    override = os.environ.get("SUBLOOM_" + name.upper().replace("-", "_") )
    candidates = [Path(override)] if override else [tools_dir() / (name + (".exe" if os.name == "nt" else ""))]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    found = shutil.which(name)
    if found:
        return str(Path(found).resolve())
    raise SubloomError(f"{name} is missing. Install the documented runtime assets or set SUBLOOM_{name.upper().replace('-', '_')}.")


@dataclass(frozen=True)
class AudioTrack:
    index: int
    codec: str
    sample_rate: int
    channels: int
    language: str
    title: str
    default: bool

    @property
    def label(self) -> str:
        return f"Track {self.index} · {self.language} · {self.codec} · {self.channels} ch" + (f" · {self.title}" if self.title else "")


@dataclass(frozen=True)
class Media:
    path: str
    duration_ms: int
    video_index: int | None
    width: int
    height: int
    frame_rate: str
    audio_tracks: list[AudioTrack]

    @property
    def default_track(self) -> int:
        return next((t.index for t in self.audio_tracks if t.default), self.audio_tracks[0].index)

    def to_dict(self) -> dict:
        return asdict(self)


def probe(path: Path, cancel: Cancellation) -> Media:
    if not path.is_file():
        raise SubloomError("This file cannot be found. Select a local video or audio file.")
    args = [executable("ffprobe"), "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json=compact=1", str(path.resolve())]
    try:
        data = json.loads(run(args, cancel, timeout=45))
        streams = data.get("streams", [])
        audios = [AudioTrack(int(s["index"]), s.get("codec_name", "unknown"), int(s.get("sample_rate", 0)),
                            int(s.get("channels", 0)), s.get("tags", {}).get("language", "und"),
                            s.get("tags", {}).get("title", ""), bool(s.get("disposition", {}).get("default")))
                  for s in streams if s.get("codec_type") == "audio"]
        if not audios:
            raise SubloomError("This file has no audio stream. Choose a recording with speech.")
        video = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
        duration = data.get("format", {}).get("duration")
        if not duration:
            duration = max((float(s.get("duration", 0)) for s in streams), default=0)
        duration_ms = round(float(duration) * 1000)
        if duration_ms <= 0:
            raise SubloomError("The media duration could not be read. Remux the file with FFmpeg and try again.")
        return Media(str(path.resolve()), duration_ms, int(video["index"]) if video else None,
                     int(video.get("width", 0)) if video else 0, int(video.get("height", 0)) if video else 0,
                     video.get("avg_frame_rate", "0/1") if video else "0/1", audios)
    except (ValueError, KeyError) as exc:
        raise SubloomError("FFprobe returned invalid media information; this file may be corrupt or unsupported.") from exc


def prepare_audio(media: Media, track: int, destination: Path, start_ms: int, length_ms: int,
                  cancel: Cancellation, progress: Progress) -> None:
    if track not in {t.index for t in media.audio_tracks}:
        raise SubloomError("The selected audio track does not exist.")
    progress("Preparing 16 kHz mono audio", None)
    run([executable("ffmpeg"), "-v", "error", "-nostdin", "-n", "-ss", f"{start_ms / 1000:.3f}",
         "-protocol_whitelist", "file,pipe", "-i", media.path, "-t", f"{length_ms / 1000:.3f}", "-map", f"0:{track}", "-vn", "-ac", "1",
         "-ar", "16000", "-c:a", "pcm_s16le", str(destination)], cancel)


def filter_path(path: Path | str) -> str:
    """Two FFmpeg parsing layers; filenames never pass through a shell."""
    text = str(path).replace("\\", "/")
    # Escape option-layer specials, then graph-layer specials (including quote).
    text = re.sub(r"([\\':])", r"\\\1", text)
    return re.sub(r"([\\'\[\],;])", r"\\\1", text)


def burn_video(media: Media, track: int, items: list[SubtitleSegment], destination: Path,
               cancel: Cancellation, progress: Progress, cache: Path, crf: int = 18) -> Path:
    if media.video_index is None:
        raise SubloomError("MP4 export requires a video source. Choose SRT, VTT or TXT for audio.")
    ensure_new_destination(destination, Path(media.path))
    if not 16 <= crf <= 24:
        raise SubloomError("Video quality CRF must be between 16 and 24.")
    filters = run([executable("ffmpeg"), "-hide_banner", "-filters"], cancel, timeout=15)
    if not re.search(r"\bsubtitles\s+", filters):
        raise SubloomError("This FFmpeg build lacks the libass subtitles filter. Install the documented build.")
    cache.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < 64 * 1024**2:
        raise SubloomError("Not enough disk space to begin video export.")
    fd, staged = tempfile.mkstemp(prefix=".subloom-", suffix=".mp4", dir=destination.parent)
    os.close(fd)
    stage = Path(staged)
    try:
        with tempfile.TemporaryDirectory(prefix="export-", dir=cache) as tmp:
            work = Path(tmp)
            # Use a safe relative filename to avoid Windows drive/Unicode/quote filter ambiguity.
            (work / "captions.srt").write_text(render(items, "srt"), encoding="utf-8")
            selected = next(t for t in media.audio_tracks if t.index == track)
            audio_codec = "copy" if selected.codec in {"aac", "mp3", "ac3", "eac3", "alac"} else "aac"

            def line(text: str) -> None:
                if text.startswith("out_time_us="):
                    try:
                        value = int(text.split("=", 1)[1]) / (media.duration_ms * 1000)
                        progress("Encoding captioned MP4", min(1.0, max(0.0, value)))
                    except ValueError:
                        pass

            progress("Encoding captioned MP4 · H.264 high quality", None)
            caption_font = "Nirmala UI" if os.name == "nt" else "Noto Sans Devanagari"
            args = [executable("ffmpeg"), "-hide_banner", "-v", "error", "-nostdin", "-y", "-protocol_whitelist", "file,pipe", "-i", media.path,
                    "-map", f"0:{media.video_index}", "-map", f"0:{track}", "-vf",
                    f"subtitles=filename=captions.srt:force_style='FontName={caption_font},FontSize=22,Outline=2,MarginV=24'",
                    "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                    "-fps_mode", "passthrough", "-c:a", audio_codec]
            if audio_codec == "aac":
                args += ["-b:a", "192k"]
            args += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(stage)]
            run(args, cancel, cwd=work, line=line)
            cancel.check()
            # Recheck to avoid replacing a file created while encoding.
            ensure_new_destination(destination, Path(media.path))
            if os.name == "nt":
                stage.rename(destination)
            else:
                os.link(stage, destination)
                stage.unlink()
            return destination
    finally:
        stage.unlink(missing_ok=True)
