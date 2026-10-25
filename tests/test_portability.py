import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from subloom.hardware import Hardware
from subloom.media import AudioTrack, Media
from subloom.models import ModelManager
from subloom.whisper_engine import WhisperEngine
from package_release import source_archive, source_files


def test_nested_pytest_base_directory_has_parent_on_clean_checkout(tmp_path):
    from conftest import pytest_configure
    base = tmp_path / "fresh-checkout" / ".test-data" / "ci"
    pytest_configure(SimpleNamespace(getoption=lambda _name: str(base)))
    assert base.parent.is_dir()
    assert not base.exists()  # Let pytest own its cleanup/create lifecycle.


def test_user_data_directory_respects_environment_and_platform(tmp_path, monkeypatch):
    from subloom import paths
    monkeypatch.setenv("SUBLOOM_DATA_DIR", str(tmp_path / "explicit"))
    assert paths.data_dir() == (tmp_path / "explicit").resolve()
    monkeypatch.delenv("SUBLOOM_DATA_DIR")
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert paths.data_dir() == (tmp_path / "xdg" / "subloom").resolve()
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert paths.data_dir() == (tmp_path / "local" / "Subloom").resolve()


@pytest.mark.parametrize("gpu_name", ["Generic CUDA device A", "Generic CUDA device B"])
def test_gpu_name_does_not_change_decoding_or_attention(tmp_path, monkeypatch, cancel, gpu_name):
    import subloom.whisper_engine as module
    monkeypatch.setattr(module, "detect", lambda: Hardware(8, 16, 8, gpu_name, 4096, "driver"))
    monkeypatch.setattr(module, "prepare_audio", lambda *_a: None)
    engine = WhisperEngine(ModelManager(tmp_path), tmp_path)
    monkeypatch.setattr(engine, "validate_cli", lambda *_a: None)
    monkeypatch.setattr(engine, "gpu_cli", lambda: tmp_path / "whisper-cli")
    seen = []
    def run(_args, _cancel, **kwargs):
        work = kwargs["cwd"]
        seen.extend((work / "arguments.txt").read_text(encoding="utf-8").splitlines())
        kwargs["line"]("whisper_backend_init_gpu: using CUDA0 backend")
        (work / "result.json").write_text(json.dumps({"model": {"multilingual": True}, "transcription": [
            {"offsets": {"from": 0, "to": 900}, "text": "recognized"}]}))
        return ""
    monkeypatch.setattr(module, "run", run)
    media = Media("sample.wav", 1000, None, 0, 0, "0/1", [AudioTrack(0, "pcm_s16le", 16000, 1, "en", "", True)])
    assert engine._infer(media, 0, "small", "Performance", "en", False, True, cancel, lambda *_a: None)
    assert "--no-flash-attn" not in seen and "--beam-size" not in seen
    assert seen[seen.index("--model") + 1] == str(engine.models.path("small"))


def test_source_archive_excludes_environments_models_media_and_private_state(tmp_path):
    root = tmp_path / "project"
    allowed = ["README.md", "LICENSE", "Dockerfile", ".gitignore", "src/subloom/app.py",
               "src/subloom/model_manifest.json", "packaging/Subloom.spec", "licenses/notice.txt", "licenses/backend/LICENSE",
               ".github/workflows/ci.yml", "tests/test_example.py"]
    excluded = [".env", ".venv/secret.py", ".tools/runtime/whisper-cli.exe", "models/weights.bin",
                "src/subloom/settings.json", "src/subloom/current.session.json", "src/subloom/checkpoint.json",
                "src/subloom/credentials.json", "tests/fixtures/private.txt",
                "src/subloom/__pycache__/app.pyc", "src/subloom.egg-info/SOURCES.txt", "tests/fixtures/private.wav",
                "dist/private.zip", ".test-data/recording.mp4", "build/developer.json"]
    for name in allowed + excluded:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test payload", encoding="utf-8")
    selected = {path.relative_to(root).as_posix() for path in source_files(root)}
    assert selected == set(allowed)
    output = tmp_path / "source.zip"
    source_archive(root, output)
    with zipfile.ZipFile(output) as archive:
        names = {name.split("/", 1)[1] for name in archive.namelist()}
        assert names == set(allowed)
        assert not any(name.startswith("/") or ".." in Path(name).parts for name in archive.namelist())
