"""Explicit model downloads. No media upload or startup network operation."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request

from .errors import SubloomError
from .process import Cancellation, Progress

MANIFEST = json.loads(Path(__file__).with_name("model_manifest.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Model:
    id: str
    name: str
    bytes: int
    sha256: str
    description: str

    @property
    def filename(self) -> str:
        return f"ggml-{self.id}.bin"

    @property
    def url(self) -> str:
        return f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{MANIFEST['revision']}/{self.filename}"


MODELS = {item["id"]: Model(**item) for item in MANIFEST["models"]}


def verify(path: Path, model: Model, cancel: Cancellation, progress: Progress = lambda *_: None) -> None:
    if not path.is_file() or path.stat().st_size != model.bytes:
        raise SubloomError(f"Whisper {model.id.title()} is missing or has an incorrect size. Import or download it again.")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            cancel.check()
            digest.update(block)
            size += len(block)
            progress("Verifying model SHA-256", size / model.bytes)
    if digest.hexdigest() != model.sha256:
        raise SubloomError("Model checksum mismatch. Delete the damaged model and download or import it again.")


class ModelManager:
    def __init__(self, directory: Path):
        self.directory = directory.expanduser().resolve()

    def path(self, model_id: str) -> Path:
        return self.directory / MODELS[model_id].filename

    def installed(self, model_id: str) -> bool:
        path = self.path(model_id)
        return path.is_file() and path.stat().st_size == MODELS[model_id].bytes

    def delete(self, model_id: str) -> None:
        self.path(model_id).unlink(missing_ok=True)

    def _stage(self, model: Model) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(self.directory).free < model.bytes + 32 * 1024**2:
            raise SubloomError("Not enough disk space for this model. Choose another model folder or free space.")
        fd, name = tempfile.mkstemp(prefix=model.id + "-", suffix=".part", dir=self.directory)
        import os
        os.close(fd)
        return Path(name)

    def import_model(self, model_id: str, source: Path, cancel: Cancellation, progress: Progress) -> Path:
        model = MODELS[model_id]
        verify(source, model, cancel, progress)
        target = self.path(model_id)
        if source.resolve() == target.resolve():
            return target
        stage = self._stage(model)
        try:
            with source.open("rb") as inp, stage.open("wb") as out:
                while block := inp.read(1024 * 1024):
                    cancel.check()
                    out.write(block)
            verify(stage, model, cancel, progress)
            cancel.check()
            stage.replace(target)
        finally:
            stage.unlink(missing_ok=True)
        return target

    def download(self, model_id: str, cancel: Cancellation, progress: Progress) -> Path:
        model = MODELS[model_id]
        if self.installed(model_id):
            verify(self.path(model_id), model, cancel, progress)
            return self.path(model_id)
        stage = self._stage(model)
        try:
            request = urllib.request.Request(model.url, headers={"User-Agent": "Subloom/0.2"})
            # Fixed trusted URL only. No source identity, media or transcript is sent.
            with urllib.request.urlopen(request, timeout=10) as response, stage.open("wb") as handle:
                received = 0
                while block := response.read(256 * 1024):
                    cancel.check()
                    received += len(block)
                    if received > model.bytes:
                        raise SubloomError("The server returned a model larger than the trusted manifest.")
                    handle.write(block)
                    progress(f"Downloading Whisper {model_id.title()} · {received / 1e6:.1f} / {model.bytes / 1e6:.1f} MB",
                             received / model.bytes)
            verify(stage, model, cancel, progress)
            cancel.check()
            stage.replace(self.path(model_id))
            return self.path(model_id)
        except (OSError, ValueError) as exc:
            raise SubloomError(f"Model download failed. Check connection, disk space and folder permissions, then retry. {exc}") from exc
        finally:
            stage.unlink(missing_ok=True)
