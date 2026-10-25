import hashlib

import pytest

from subloom.errors import Cancelled, SubloomError
from subloom.media import burn_video, executable, filter_path, prepare_audio, probe
from subloom.process import Cancellation, run
from subloom.subtitles import segment


def make_media(ffmpeg, destination, cancel, video=True, extra_audio=False):
    args = [ffmpeg, "-v", "error", "-nostdin", "-n"]
    if video:
        args += ["-f", "lavfi", "-i", "color=c=0x25334d:s=640x360:r=24:d=2"]
    args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
    if extra_audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=880:duration=2"]
    if video:
        args += ["-map", "0:v", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    args += ["-map", "1:a" if video else "0:a"]
    if extra_audio:
        args += ["-map", "2:a" if video else "1:a", "-disposition:a:0", "0", "-disposition:a:1", "default"]
    suffix = destination.suffix.lower()
    codec = {".wav": "pcm_s16le", ".flac": "flac", ".mp3": "libmp3lame"}.get(suffix, "aac")
    args += ["-c:a", codec, str(destination)]
    run(args, cancel)
    return destination


@pytest.mark.integration
@pytest.mark.parametrize("extension", ["mp4", "mkv", "mov", "mp3", "wav", "flac"])
def test_valid_formats(tmp_path, ffmpeg, cancel, extension):
    path = make_media(ffmpeg, tmp_path / f"हिंदी ' unusual [{extension}].{extension}", cancel,
                      video=extension in {"mp4", "mkv", "mov"})
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    info = probe(path, cancel)
    assert 1900 <= info.duration_ms <= 2200
    assert len(info.audio_tracks) == 1
    assert (info.video_index is not None) == (extension in {"mp4", "mkv", "mov"})
    audio = tmp_path / "extracted.wav"
    prepare_audio(info, info.default_track, audio, 0, info.duration_ms, cancel, lambda *_: None)
    import wave
    with wave.open(str(audio)) as wav:
        assert wav.getframerate() == 16000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


@pytest.mark.integration
def test_multiple_tracks_and_corrupt_media(tmp_path, ffmpeg, cancel):
    path = make_media(ffmpeg, tmp_path / "multiple.mkv", cancel, extra_audio=True)
    media = probe(path, cancel)
    assert len(media.audio_tracks) == 2
    assert media.default_track == media.audio_tracks[1].index
    output = tmp_path / "selected.wav"
    prepare_audio(media, media.default_track, output, 0, 1000, cancel, lambda *_: None)
    assert output.stat().st_size > 30000
    broken = tmp_path / "corrupt.mp4"
    broken.write_bytes(b"invalid media")
    with pytest.raises(SubloomError):
        probe(broken, cancel)
    silent = tmp_path / "silent.mp4"
    run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=s=64x64:d=0.1", str(silent)], cancel)
    with pytest.raises(SubloomError, match="no audio"):
        probe(silent, cancel)


@pytest.mark.integration
def test_video_burn_preserves_source_and_quality(tmp_path, ffmpeg, cancel):
    path = make_media(ffmpeg, tmp_path / "source हिन्दी ' [test].mp4", cancel)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    media = probe(path, cancel)
    output = tmp_path / "captioned हिन्दी ' space.mp4"
    cues = [segment(0, 1800, "Visible captions · नमस्ते")]
    burn_video(media, media.default_track, cues, output, cancel, lambda *_: None, tmp_path / "cache ' हिंदी")
    result = probe(output, cancel)
    assert (result.width, result.height, result.frame_rate) == (media.width, media.height, media.frame_rate)
    assert result.audio_tracks[0].codec == media.audio_tracks[0].codec
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    raw = tmp_path / "original-frame.rgb"
    burned = tmp_path / "burned-frame.rgb"
    for src, dst in ((path, raw), (output, burned)):
        run([ffmpeg, "-v", "error", "-ss", "0.5", "-i", str(src), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(dst)], cancel)
    # Uniform original vs. captioned frame: bright glyph pixels must appear in the caption area.
    original, captioned = raw.read_bytes(), burned.read_bytes()
    start = 240 * 640 * 3
    assert sum(1 for a, b in zip(original[start:], captioned[start:]) if b > a + 70) > 100


@pytest.mark.integration
def test_burn_cancel_cleans_and_audio_only_rejected(tmp_path, ffmpeg, cancel, monkeypatch):
    path = make_media(ffmpeg, tmp_path / "source.mp4", cancel)
    media = probe(path, cancel)
    output = tmp_path / "cancelled.mp4"
    import subloom.media as module
    real_run = module.run
    def cancel_encode(args, token, **kwargs):
        if "libx264" in args:
            token.cancel()
        return real_run(args, token, **kwargs)
    monkeypatch.setattr(module, "run", cancel_encode)
    with pytest.raises(Cancelled):
        burn_video(media, media.default_track, [segment(0, 1000, "Hi")], output, cancel, lambda *_: None, tmp_path)
    assert not output.exists() and not list(tmp_path.glob(".subloom-*"))
    cancel = Cancellation()
    audio_path = make_media(ffmpeg, tmp_path / "audio.wav", cancel, video=False)
    audio = probe(audio_path, cancel)
    with pytest.raises(SubloomError, match="video source"):
        burn_video(audio, audio.default_track, [], output, cancel, lambda *_: None, tmp_path)


def test_ffmpeg_filter_windows_escaping():
    assert filter_path("C:\\Users\\A B\\हिंदी's [file].srt") == "C\\\\:/Users/A B/हिंदी\\\\\\'s \\[file\\].srt"


def test_missing_dependency(monkeypatch):
    monkeypatch.setenv("SUBLOOM_FFPROBE", "/nonexistent/ffprobe")
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(SubloomError, match="missing"):
        executable("ffprobe")
