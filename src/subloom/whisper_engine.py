"""Adapter for the verified whisper.cpp v1.8.3 whisper-cli interface."""
from dataclasses import replace
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import hashlib
import time

from .errors import GPUError, SubloomError
from .hardware import detect, threads
from .media import Media, executable, prepare_audio
from .models import MODELS, ModelManager, verify
from .process import Cancellation, Progress, run
from .subtitles import SubtitleSegment, segment
from .paths import data_dir, tools_dir
from .session import atomic_json

_INFERENCE_LOCK = threading.Lock()
CHUNK_MS = 300_000
OVERLAP_MS = 2_000


def parse_output(data: dict, duration_ms: int, offset_ms: int = 0) -> list[SubtitleSegment]:
    if not data.get("model", {}).get("multilingual", False):
        raise SubloomError("A multilingual Whisper Base, Small or Medium model is required; .en models are unsupported.")
    output = []
    try:
        for item in data["transcription"]:
            start = max(0, int(item["offsets"]["from"]) + offset_ms)
            end = min(duration_ms, int(item["offsets"]["to"]) + offset_ms)
            text = item["text"].strip()
            if text and start < end:
                output.append(segment(start, end, text))
    except (TypeError, KeyError, ValueError) as exc:
        raise SubloomError("whisper-cli returned invalid timecoded JSON. Use the pinned v1.8.3 runtime.") from exc
    return output


class WhisperEngine:
    def __init__(self, models: ModelManager, cache: Path, source: dict | None = None, fast_decode: bool = False):
        self.models = models
        self.cache = cache.resolve()
        self.source = source
        self.last_backend = ""
        self.fast_decode = fast_decode

    @staticmethod
    def gpu_cli() -> Path | None:
        # Only a separately supplied CUDA build is eligible. Mere NVIDIA detection is insufficient.
        configured = os.environ.get("SUBLOOM_GPU_CLI")
        if configured:
            candidate = Path(configured)
            return candidate.resolve() if candidate.is_file() else None
        candidate = tools_dir() / "gpu" / "whisper-cli.exe"
        if candidate.is_file():
            return candidate.resolve()
        candidate = data_dir() / "runtimes" / "gpu" / "whisper-cli.exe"
        return candidate.resolve() if candidate.is_file() else None

    @staticmethod
    def validate_cli(cli: str, cancel: Cancellation) -> None:
        help_text = run([cli, "--help"], cancel, timeout=15)
        for flag in ["--output-json", "--output-file", "--no-gpu", "--translate", "--print-progress", "--language"]:
            if flag not in help_text:
                raise SubloomError("Incompatible whisper-cli. Install the pinned whisper.cpp v1.8.3 runtime.")

    def infer(self, media: Media, track: int, model_id: str, profile: str, device: str,
              language: str, translate: bool, cancel: Cancellation, progress: Progress) -> list[SubtitleSegment]:
        if not _INFERENCE_LOCK.acquire(blocking=False):
            raise SubloomError("Another local inference job is running. Wait or cancel it first.")
        try:
            verify(self.models.path(model_id), MODELS[model_id], cancel, progress)
            self.cache.mkdir(parents=True, exist_ok=True)
            use_gpu = device == "GPU" or (device == "Auto" and profile != "Eco" and
                                          bool(detect().gpu_name) and self.gpu_cli() is not None)
            if use_gpu and self.gpu_cli() is None:
                raise GPUError("GPU requires a separately installed compatible CUDA whisper.cpp build. Choose CPU or configure SUBLOOM_GPU_CLI.")
            try:
                return self._infer(media, track, model_id, profile, language, translate, use_gpu, cancel, progress)
            except SubloomError as exc:
                from .errors import Cancelled
                if isinstance(exc, Cancelled) or not use_gpu:
                    raise
                if device == "Auto":
                    progress("GPU unavailable. Auto is retrying on CPU with the same model.", None)
                    return self._infer(media, track, model_id, profile, language, translate, False, cancel, progress)
                raise GPUError(f"GPU inference failed: {exc}\nChoose Retry on CPU to keep the same model.") from exc
        finally:
            _INFERENCE_LOCK.release()

    def _infer(self, media: Media, track: int, model_id: str, profile: str, language: str,
               translate: bool, gpu: bool, cancel: Cancellation, progress: Progress) -> list[SubtitleSegment]:
        cli = str(self.gpu_cli()) if gpu else executable("whisper-cli")
        self.validate_cli(cli, cancel)
        results: list[SubtitleSegment] = []
        gpu_confirmed = False
        checkpoint_path = self.cache / "inference.checkpoint.json"
        checkpoint_key = hashlib.sha256(json.dumps({"source": self.source, "model": MODELS[model_id].sha256,
            "track": track, "profile": profile, "language": language, "translation": translate,
            "gpu": gpu, "fast_decode": self.fast_decode, "chunk_ms": CHUNK_MS,
            "overlap_ms": OVERLAP_MS, "adapter": 4}, sort_keys=True).encode()).hexdigest()
        resume_ms = 0
        if self.source and checkpoint_path.is_file():
            try:
                saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                if saved.get("key") == checkpoint_key:
                    resume_ms = int(saved["completed_ms"])
                    if not 0 <= resume_ms <= media.duration_ms or (resume_ms != media.duration_ms and resume_ms % CHUNK_MS):
                        raise ValueError("Invalid checkpoint boundary")
                    results = [SubtitleSegment(**s).validate(media.duration_ms) for s in saved["segments"]]
                    progress(f"Resuming saved progress · {resume_ms // 60000} minutes already completed", resume_ms / media.duration_ms)
            except (ValueError, KeyError, TypeError, OSError, SubloomError):
                resume_ms, results = 0, []
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="asr-", dir=self.cache) as temporary:
            work = Path(temporary)
            for start in range(resume_ms, media.duration_ms, CHUNK_MS):
                cancel.check()
                audio_start = max(0, start - OVERLAP_MS)
                central_end = min(start + CHUNK_MS, media.duration_ms)
                audio_end = min(central_end + OVERLAP_MS, media.duration_ms)
                wav = work / "audio.wav"
                wav.unlink(missing_ok=True)
                prepare_audio(media, track, wav, audio_start, audio_end - audio_start, cancel, progress)
                output = work / "result"
                output.with_suffix(".json").unlink(missing_ok=True)
                task = "Translating audio into English" if translate else "Transcribing locally"
                part_label = f"Part {start // CHUNK_MS + 1}/{(media.duration_ms + CHUNK_MS - 1) // CHUNK_MS}"

                def line(text: str) -> None:
                    nonlocal gpu_confirmed
                    # Actual backend initialization must confirm CUDA offload, not just a GPU build.
                    if re.search(r"whisper_backend_init_gpu: using CUDA\d* backend", text, re.I):
                        gpu_confirmed = True
                    if "progress" in text:
                        match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
                        if match:
                            part = float(match.group(1)) / 100
                            completed = start + (central_end - start) * part
                            label = f"{task} · {'NVIDIA GPU' if gpu else 'CPU'} · {part_label}"
                            measured_ms = completed - resume_ms
                            if measured_ms >= 30_000:
                                remaining = (time.monotonic() - started) * (media.duration_ms - completed) / measured_ms
                                label += f" · ~{max(1, round(remaining / 60))} min for this pass (estimate)"
                            progress(label, min(1.0, completed / media.duration_ms))

                progress(f"Loading model · {('CUDA GPU validation' if gpu else 'CPU')} · {part_label}", None)
                args = [cli, "--model", str(self.models.path(model_id)), "--file", "audio.wav",
                        "--language", language, "--threads", str(threads(profile)), "--processors", "1",
                        "--output-json", "--output-file", "result", "--print-progress"]
                if translate:
                    args += ["--translate"]
                if not gpu:
                    args += ["--no-gpu"]
                if self.fast_decode:
                    # Explicit opt-in: fewer decoding candidates can reduce
                    # recognition quality. Never change the chosen model.
                    args += ["--beam-size", "1", "--best-of", "1"]
                # The pinned Windows CLI's main(argv) uses the system code page.
                # Its documented/source-verified response-file path accepts UTF-8
                # model arguments. WAV/output are ASCII paths relative to the
                # Unicode-safe CreateProcessW working directory.
                if any("\n" in arg or "\r" in arg for arg in args[1:]):
                    raise SubloomError("Choose a model folder without line breaks in its name.")
                (work / "arguments.txt").write_text("\n".join(args[1:]) + "\n", encoding="utf-8")
                run([cli, "@arguments.txt"], cancel, cwd=work, line=line)
                if gpu and not gpu_confirmed:
                    raise GPUError("The supplied backend did not confirm CUDA initialization; GPU acceleration is not validated.")
                self.last_backend = "NVIDIA GPU" if gpu else "CPU"
                try:
                    data = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise SubloomError("Whisper did not produce valid JSON. Check the pinned backend and model.") from exc
                items = parse_output(data, media.duration_ms, audio_start)
                # Assign overlapping chunks by segment midpoint. Clamp boundaries to prevent
                # duplicate cues and out-of-order timestamps; never manufacture word alignment.
                for item in items:
                    midpoint = (item.start_ms + item.end_ms) / 2
                    if start <= midpoint < central_end:
                        cue = replace(item, start_ms=max(start, item.start_ms), end_ms=min(central_end, item.end_ms))
                        if cue.start_ms < cue.end_ms:
                            results.append(cue)
                if self.source:
                    # Checkpoint only completed chunks, with source SHA-256 and all
                    # inference settings. Cancellation never caches half a chunk.
                    atomic_json(checkpoint_path, {"key": checkpoint_key, "completed_ms": central_end,
                                                 "segments": [s.to_dict() for s in results]})
        if not results:
            raise SubloomError("No speech was detected. Check the audio track and recording volume, or try another model.")
        return sorted(results, key=lambda s: s.start_ms)
