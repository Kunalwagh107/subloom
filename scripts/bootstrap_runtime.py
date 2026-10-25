"""Explicit download of pinned, checksummed Windows CPU runtime assets.

No downloads occur at application startup. Run this only when installing Subloom.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ASSETS = [
    {"name": "whisper.cpp", "version": "1.8.3", "url": "https://github.com/ggml-org/whisper.cpp/releases/download/v1.8.3/whisper-bin-x64.zip",
     "sha256": "d824b1e37599f882b396e73f1ee0bfd5d0529f700314c48311dcbd00b803321d", "bytes": 3968674},
    {"name": "FFmpeg", "version": "7.1.1", "url": "https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip",
     "sha256": "04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4"},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Explicitly authorize installation-asset downloads")
    parser.add_argument("--archives", type=Path, help="Offline folder containing whisper.zip and ffmpeg.zip")
    parser.add_argument("--destination", type=Path, default=Path(".tools/runtime"))
    parser.add_argument("--gpu", action="store_true", help="Also install the pinned optional CUDA runtime")
    parser.add_argument("--gpu-archive", type=Path, help="Offline pinned CUDA ZIP (requires --gpu)")
    args = parser.parse_args()
    if not args.download and not args.archives:
        parser.error("Use --download to authorize downloads, or --archives for an offline installation.")
    args.destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.destination.parent) as temporary:
        work = Path(temporary)
        for asset, filename in zip(ASSETS, ["whisper.zip", "ffmpeg.zip"]):
            archive = args.archives / filename if args.archives else work / filename
            if not args.archives:
                print(f"Downloading {asset['name']} {asset['version']} from {asset['url']}", flush=True)
                with urllib.request.urlopen(asset["url"], timeout=30) as response, archive.open("wb") as out:
                    shutil.copyfileobj(response, out, 1024 * 1024)
            with archive.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            if digest != asset["sha256"]:
                raise SystemExit(f"Checksum mismatch for {asset['name']}; no files installed from it.")
            extracted = work / asset["name"]
            with zipfile.ZipFile(archive) as package:
                for member in package.infolist():
                    target = (extracted / member.filename).resolve()
                    if not target.is_relative_to(extracted.resolve()):
                        raise SystemExit("Unsafe archive entry")
                package.extractall(extracted)
            wanted = {"whisper-cli.exe", "ffmpeg.exe", "ffprobe.exe", "whisper.dll", "ggml.dll", "ggml-base.dll", "ggml-cpu.dll"}
            for path in extracted.rglob("*"):
                if path.is_file() and path.name in wanted:
                    shutil.copy2(path, args.destination / path.name)
                if path.is_file() and path.name in {"LICENSE", "README.txt"}:
                    license_dir = args.destination / "licenses" / asset["name"]
                    license_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, license_dir / path.name)
    assets = list(ASSETS)
    if args.gpu:
        from subloom.runtime import GPU_ASSET, install_gpu
        from subloom.process import Cancellation
        install_gpu(args.destination / "gpu", Cancellation(), lambda step, _value: None, args.gpu_archive)
        assets.append({"name": "Optional CUDA", **GPU_ASSET})
    (args.destination / "runtime-manifest.json").write_text(json.dumps(assets, indent=2), encoding="utf-8")
    print(f"CPU runtime ready at {args.destination}. No models were downloaded.")


if __name__ == "__main__":
    main()
