"""Explicit, pinned installation of the optional NVIDIA runtime; no startup downloads."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

from .errors import SubloomError
from .process import Cancellation, Progress

GPU_ASSET = {
    "url": "https://github.com/ggml-org/whisper.cpp/releases/download/v1.8.3/whisper-cublas-12.4.0-bin-x64.zip",
    "bytes": 459854042,
    "sha256": "c12a563333d3c3707be70754dc0e87c1cb58aa6333a87055bbcf9b524488dfb0",
    "version": "whisper.cpp 1.8.3 / CUDA 12.4",
}
GPU_FILES = {"whisper-cli.exe", "whisper.dll", "ggml.dll", "ggml-base.dll", "ggml-cpu.dll", "ggml-cuda.dll",
             "cublas64_12.dll", "cublasLt64_12.dll", "cudart64_12.dll", "nvrtc-builtins64_124.dll", "nvrtc64_120_0.dll"}


def install_gpu(destination: Path, cancel: Cancellation, progress: Progress, archive: Path | None = None) -> Path:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < 1600 * 1024**2:
        raise SubloomError("GPU support needs about 1.6 GB of free space during installation. CPU still works.")
    with tempfile.TemporaryDirectory(prefix="gpu-install-", dir=destination.parent) as temporary:
        work = Path(temporary)
        package = archive or work / "cuda.zip"
        if archive is None:
            request = urllib.request.Request(GPU_ASSET["url"], headers={"User-Agent": "Subloom/0.2"})
            try:
                with urllib.request.urlopen(request, timeout=15) as response, package.open("wb") as output:
                    received = 0
                    while block := response.read(1024 * 1024):
                        cancel.check()
                        received += len(block)
                        if received > GPU_ASSET["bytes"]:
                            raise SubloomError("GPU download exceeds the pinned asset size.")
                        output.write(block)
                        progress("Downloading optional GPU support · 460 MB", received / GPU_ASSET["bytes"])
            except OSError as exc:
                raise SubloomError(f"GPU support download failed. Check the connection and retry. {exc}") from exc
        if package.stat().st_size != GPU_ASSET["bytes"]:
            raise SubloomError("GPU runtime archive has the wrong size. Download it again.")
        digest = hashlib.sha256()
        with package.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                cancel.check()
                digest.update(block)
        if digest.hexdigest() != GPU_ASSET["sha256"]:
            raise SubloomError("GPU support checksum mismatch. No runtime files were installed.")
        staged = work / "runtime"
        staged.mkdir()
        with zipfile.ZipFile(package) as zipped:
            for member in zipped.infolist():
                name = Path(member.filename).name
                if name in GPU_FILES:
                    cancel.check()
                    progress(f"Installing GPU runtime · {name}", None)
                    with zipped.open(member) as src, (staged / name).open("wb") as dst:
                        while block := src.read(1024 * 1024):
                            cancel.check()
                            dst.write(block)
        if not all((staged / name).is_file() for name in GPU_FILES):
            raise SubloomError("The GPU runtime archive is incomplete. CPU processing is still available.")
        cancel.check()
        backup = work / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
        progress("GPU support installed · execution will validate your device", 1.0)
    return destination / "whisper-cli.exe"
