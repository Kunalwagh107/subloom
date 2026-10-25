from dataclasses import asdict, dataclass, replace
from pathlib import Path
import html
import re
import uuid

from .errors import SubloomError


@dataclass(frozen=True)
class SubtitleSegment:
    id: str
    start_ms: int
    end_ms: int
    text: str

    def validate(self, duration_ms: int | None = None) -> "SubtitleSegment":
        if not self.id or not isinstance(self.text, str):
            raise SubloomError("Invalid subtitle segment.")
        if not isinstance(self.start_ms, int) or not isinstance(self.end_ms, int):
            raise SubloomError("Caption times must be integer milliseconds.")
        if not 0 <= self.start_ms < self.end_ms:
            raise SubloomError("Caption start must be nonnegative and earlier than its end.")
        if duration_ms is not None and self.end_ms > duration_ms:
            raise SubloomError("Caption end must be within the media duration.")
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def segment(start: int, end: int, text: str) -> SubtitleSegment:
    return SubtitleSegment(uuid.uuid4().hex, start, end, text).validate()


def clone(items: list[SubtitleSegment]) -> list[SubtitleSegment]:
    return [replace(item) for item in items]


def timestamp(ms: int, separator: str = ",") -> str:
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, milli = divmod(rest, 1000)
    return f"{h:02}:{m:02}:{s:02}{separator}{milli:03}"


def parse_time(text: str) -> int:
    match = re.fullmatch(r"(\d+):([0-5]\d):([0-5]\d)[,.](\d{3})", text.strip())
    if not match:
        raise SubloomError("Use HH:MM:SS.mmm for times, for example 00:01:23.450.")
    h, m, s, ms = map(int, match.groups())
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def render(items: list[SubtitleSegment], fmt: str, timed_text: bool = False) -> str:
    ordered = sorted(items, key=lambda x: (x.start_ms, x.end_ms))
    for item in ordered:
        item.validate()
    if fmt == "txt":
        return "\n".join((f"[{timestamp(s.start_ms, '.')}] " if timed_text else "") + s.text
                         for s in ordered) + "\n"
    if fmt not in {"srt", "vtt"}:
        raise SubloomError("Choose SRT, VTT or TXT.")
    sep = "," if fmt == "srt" else "."
    cues = []
    for index, s in enumerate(ordered, 1):
        text = html.escape(s.text.replace("\r", "").strip(), quote=False)
        text = re.sub(r"\n\s*\n", "\n", text)
        cues.append(f"{index}\n{timestamp(s.start_ms, sep)} --> {timestamp(s.end_ms, sep)}\n{text}\n")
    return ("WEBVTT\n\n" if fmt == "vtt" else "") + "\n".join(cues)


def ensure_new_destination(destination: Path, source: Path | None = None) -> None:
    if source and destination.resolve() == source.resolve():
        raise SubloomError("Choose a different destination. Original media is never overwritten.")
    if destination.exists():
        raise SubloomError("That destination already exists. Choose a new name to preserve it.")
    if not destination.parent.is_dir():
        raise SubloomError("The destination folder does not exist.")


def export_text(items: list[SubtitleSegment], destination: Path, fmt: str,
                source: Path | None = None, timed_text: bool = False) -> None:
    ensure_new_destination(destination, source)
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(render(items, fmt, timed_text))
