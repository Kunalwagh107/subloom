from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import tempfile
import shutil
from typing import Any

from .errors import SubloomError
from .process import Cancellation
from .subtitles import SubtitleSegment, clone

CACHE_VERSION = 1


def identity(path: Path, cancel: Cancellation) -> dict:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            cancel.check()
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SubloomError("The recording changed during import. Wait for copying to finish and import again.")
    return {"path": str(path.resolve()), "bytes": after.st_size, "mtime_ns": after.st_mtime_ns,
            "sha256": digest.hexdigest()}


def cache_key(source: dict, model_id: str, model_hash: str, settings: dict) -> str:
    data = {"version": CACHE_VERSION, "source": source, "engine": "whisper.cpp-v1.8.3",
            "model": model_id, "model_hash": model_hash, "settings": settings}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def assert_source_unchanged(source: dict) -> None:
    if not {"path", "bytes", "mtime_ns"}.issubset(source):
        return
    try:
        stat = Path(source["path"]).stat()
    except OSError as exc:
        raise SubloomError("The recording is no longer available. Import it again.") from exc
    if (stat.st_size, stat.st_mtime_ns) != (source["bytes"], source["mtime_ns"]):
        raise SubloomError("The recording changed after import. Import it again to invalidate old cached captions.")


def save_session(path: Path, session: "Session") -> None:
    if path.exists():
        old = load_session(path)
        if old and old.key != session.key:
            # One recovery snapshot, not a project database. Preserve the last
            # result before a different recording/model/settings replaces it.
            backup = path.with_name("previous.session.json")
            shutil.copy2(path, backup)
    atomic_json(path, session.to_dict())


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".save-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        Path(name).replace(path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass
class Session:
    source: dict
    duration_ms: int
    model_id: str
    settings: dict
    key: str
    raw: list[SubtitleSegment] = field(default_factory=list)
    generated: dict[str, list[SubtitleSegment]] = field(default_factory=dict)
    edits: dict[str, list[SubtitleSegment]] = field(default_factory=dict)
    mode: str = "hinglish"

    def captions(self, mode: str) -> list[SubtitleSegment]:
        return clone(self.edits.get(mode, self.generated.get(mode, [])))

    def to_dict(self) -> dict:
        return {"version": CACHE_VERSION, "source": self.source, "duration_ms": self.duration_ms,
                "engine": "whisper.cpp-v1.8.3", "model_id": self.model_id, "settings": self.settings,
                "key": self.key, "raw": [s.to_dict() for s in self.raw], "mode": self.mode,
                "generated": {k: [s.to_dict() for s in v] for k, v in self.generated.items()},
                "edits": {k: [s.to_dict() for s in v] for k, v in self.edits.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        if data.get("version") != CACHE_VERSION:
            raise SubloomError("Saved session version is unsupported. Your old session was preserved.")
        duration = int(data["duration_ms"])

        def items(values: list) -> list[SubtitleSegment]:
            return [SubtitleSegment(**s).validate(duration) for s in values]

        return cls(data["source"], duration, data["model_id"], data["settings"], data["key"],
                   items(data["raw"]), {k: items(v) for k, v in data["generated"].items()},
                   {k: items(v) for k, v in data["edits"].items()}, data["mode"])


def load_session(path: Path) -> Session | None:
    if not path.exists():
        return None
    try:
        return Session.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SubloomError("The saved session cannot be read; it has been preserved. Rename it to start fresh.") from exc


def load_settings(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
