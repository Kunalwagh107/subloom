from .language import hinglish
from .media import Media
from .models import MODELS
from .process import Cancellation, Progress
from .session import Session, assert_source_unchanged, cache_key, save_session
from .subtitles import clone
from .whisper_engine import WhisperEngine
from pathlib import Path


def generate(media: Media, source: dict, model_id: str, settings: dict, mode: str,
             previous: Session | None, engine: WhisperEngine, session_path: Path,
             cancel: Cancellation, progress: Progress) -> Session:
    assert_source_unchanged(source)
    key = cache_key(source, model_id, MODELS[model_id].sha256, settings)
    session = Session.from_dict(previous.to_dict()) if previous and previous.key == key else Session(
        source, media.duration_ms, model_id, settings, key)
    session.mode = mode
    if mode in session.generated:
        progress("Opening cached captions", 1.0)
        return session
    if not session.raw:
        session.raw = engine.infer(media, settings["track"], model_id, settings["profile"], settings["device"],
                                   settings["language"], False, cancel, progress)
        session.generated["original"] = clone(session.raw)
        session.generated["hinglish"] = hinglish(session.raw)
        assert_source_unchanged(source)
        save_session(session_path, session)
    cancel.check()
    if mode == "english":
        session.generated[mode] = engine.infer(media, settings["track"], model_id, settings["profile"], settings["device"],
                                               settings["language"], True, cancel, progress)
    progress("Saving captions", None)
    assert_source_unchanged(source)
    save_session(session_path, session)
    return session
