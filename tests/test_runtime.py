import hashlib
import io
import zipfile

import pytest

from subloom.errors import Cancelled, SubloomError
from subloom.runtime import GPU_FILES, install_gpu


@pytest.fixture
def gpu_archive(tmp_path, monkeypatch):
    path = tmp_path / "runtime.zip"
    with zipfile.ZipFile(path, "w") as zipped:
        for name in GPU_FILES:
            zipped.writestr("Release/" + name, b"test-only binary payload")
        zipped.writestr("../unwanted.exe", b"not installed")
    content = path.read_bytes()
    monkeypatch.setattr("subloom.runtime.GPU_ASSET", {"url": "https://example.invalid/pinned.zip",
                        "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return path, content


def test_gpu_offline_install_verifies_and_extracts_only_whitelist(tmp_path, cancel, gpu_archive):
    path, _ = gpu_archive
    target = tmp_path / "installed"
    installed = install_gpu(target, cancel, lambda *_: None, path)
    assert installed.is_file()
    assert {p.name for p in target.iterdir()} == GPU_FILES
    assert not (tmp_path / "unwanted.exe").exists()
    assert not list(tmp_path.glob("gpu-install-*"))


def test_gpu_download_cancel_cleanup_and_hash_error(tmp_path, monkeypatch, cancel, gpu_archive):
    path, content = gpu_archive
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_k: io.BytesIO(content))
    def stop(*_):
        cancel.cancel()
    with pytest.raises(Cancelled):
        install_gpu(tmp_path / "installed", cancel, stop)
    assert not (tmp_path / "installed").exists()
    assert not list(tmp_path.glob("gpu-install-*"))
    from subloom.process import Cancellation
    path.write_bytes(b"x" * len(content))
    with pytest.raises(SubloomError, match="checksum"):
        install_gpu(tmp_path / "installed", Cancellation(), lambda *_: None, path)
