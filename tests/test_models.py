from dataclasses import replace
import hashlib
import io
import shutil
import urllib.error

import pytest

from subloom.errors import Cancelled, SubloomError
from subloom.models import MODELS, ModelManager, verify


@pytest.fixture
def tiny_model(monkeypatch):
    content = b"a-real-download-test-payload" * 1000
    original = MODELS["base"]
    test_model = replace(original, bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
    monkeypatch.setitem(MODELS, "base", test_model)
    return test_model, content


def test_download_verify_reuse_delete(tmp_path, monkeypatch, cancel, tiny_model):
    model, content = tiny_model
    requests = []
    def open_url(request, timeout):
        requests.append(request.full_url)
        return io.BytesIO(content)
    monkeypatch.setattr("urllib.request.urlopen", open_url)
    manager = ModelManager(tmp_path)
    progress = []
    path = manager.download("base", cancel, lambda *p: progress.append(p))
    assert path.read_bytes() == content
    assert len(requests) == 1 and "/resolve/5359861" in requests[0]
    assert manager.installed("base")
    assert manager.download("base", cancel, lambda *_: None) == path
    assert len(requests) == 1
    assert progress[-1][1] == 1
    manager.delete("base")
    assert not manager.installed("base")
    assert not list(tmp_path.glob("*.part"))


def test_cancel_retry_and_corruption(tmp_path, monkeypatch, cancel, tiny_model):
    model, content = tiny_model
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: io.BytesIO(content))
    manager = ModelManager(tmp_path)
    def cancelling(*_):
        cancel.cancel()
    with pytest.raises(Cancelled):
        manager.download("base", cancel, cancelling)
    assert not manager.installed("base")
    assert not list(tmp_path.glob("*.part"))
    from subloom.process import Cancellation
    path = manager.download("base", Cancellation(), lambda *_: None)
    path.write_bytes(b"x" * model.bytes)
    with pytest.raises(SubloomError, match="checksum mismatch"):
        verify(path, model, Cancellation())


def test_manual_install_and_failed_network(tmp_path, monkeypatch, cancel, tiny_model):
    model, content = tiny_model
    source = tmp_path / "offline.bin"
    source.write_bytes(content)
    manager = ModelManager(tmp_path / "models")
    manager.import_model("base", source, cancel, lambda *_: None)
    assert manager.installed("base")
    assert source.read_bytes() == content
    manager.delete("base")
    def broken(*a, **k):
        raise urllib.error.URLError("network disconnected")
    monkeypatch.setattr("urllib.request.urlopen", broken)
    with pytest.raises(SubloomError, match="download failed"):
        manager.download("base", cancel, lambda *_: None)
    assert not list(manager.directory.glob("*.part"))


def test_low_disk_space(tmp_path, monkeypatch, cancel, tiny_model):
    monkeypatch.setattr(shutil, "disk_usage", lambda _: type("Disk", (), {"free": 1})())
    with pytest.raises(SubloomError, match="disk space"):
        ModelManager(tmp_path).download("base", cancel, lambda *_: None)
