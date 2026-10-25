"""Prepare a small sharing folder and a source-only ZIP; no media or model files."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

from subloom import __version__

ROOT_FILES = {"AGENTS.md", "README.md", "LICENSE", "CONTRIBUTING.md", "pyproject.toml",
              "Dockerfile", "compose.yaml", ".gitignore", ".dockerignore"}
SOURCE_DIRS = {"src", "tests", "scripts", "packaging", "docs", "licenses", ".github"}
SOURCE_SUFFIXES = {".py", ".ps1", ".qml", ".svg", ".ico", ".spec", ".iss", ".md", ".txt", ".html", ".yml", ".yaml", ".json"}


def source_files(root: Path) -> list[Path]:
    root = root.resolve()
    selected = []
    candidates = [root / name for name in ROOT_FILES]
    for directory in SOURCE_DIRS:
        folder = root / directory
        if folder.is_dir():
            candidates.extend(folder.rglob("*"))
    for candidate in sorted(candidates):
        relative = candidate.relative_to(root)
        if relative.parts[0] not in SOURCE_DIRS and relative.as_posix() not in ROOT_FILES:
            continue
        if not candidate.is_file() or candidate.is_symlink() or not candidate.resolve().is_relative_to(root):
            continue
        if any(part.startswith(".") or part == "__pycache__" or part.endswith((".egg-info", ".dist-info"))
               for part in relative.parts[1:]):
            continue
        name = candidate.name.lower()
        if (name == "settings.json" or "checkpoint" in name or name.endswith(".session.json")
                or name.startswith(".env")):
            continue
        if candidate.suffix.lower() == ".json" and relative.as_posix() != "src/subloom/model_manifest.json":
            continue
        if candidate.suffix.lower() == ".txt" and relative.parts[0] != "licenses" and not name.startswith("requirements"):
            continue
        license_notice = relative.parts[0] == "licenses" and name in {"license", "copying", "notice"}
        if relative.as_posix() in ROOT_FILES or candidate.suffix.lower() in SOURCE_SUFFIXES or license_notice:
            selected.append(candidate)
    return selected


def source_archive(root: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files(root):
            archive.write(path, f"Subloom-{__version__}-source/{path.relative_to(root).as_posix()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Default: dist/share")
    parser.add_argument("--source-only", action="store_true", help="Do not require compiled Windows installers")
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "dist" / "share").resolve()
    output.mkdir(parents=True, exist_ok=True)
    core_name = f"Subloom-Setup-{__version__}.exe"
    gpu_name = f"Subloom-NVIDIA-Setup-{__version__}.exe"
    if not args.source_only:
        core = root / "dist" / "installers" / core_name
        if not core.is_file():
            parser.error("Build the Windows installer first, or use --source-only.")
        shutil.copy2(core, output / core.name)
        gpu = root / "dist" / "installers" / gpu_name
        if gpu.is_file():
            shutil.copy2(gpu, output / gpu.name)
    source_archive(root, output / f"Subloom-{__version__}-source.zip")
    for source in (root / "README.md", root / "LICENSE", root / "CONTRIBUTING.md",
                   root / "docs" / "USER_GUIDE.md", root / "docs" / "THIRD_PARTY.md"):
        shutil.copy2(source, output / source.name)
    docs = output / "docs"
    docs.mkdir(exist_ok=True)
    for source in sorted((root / "docs").glob("*.md")):
        shutil.copy2(source, docs / source.name)
    installation = ("Extract the source ZIP and follow README.md to build or run from source.\n\n"
                    if args.source_only else
                    f"Windows users: run `{core_name}`. Python and Docker are not required.\n\n")
    guide = (f"# Subloom {__version__}\n\n"
             + installation +
             f"Optional NVIDIA support: run `{gpu_name}` if supplied, or enable it in the app. "
             "A compatible driver is required. CPU processing remains available.\n\n"
             "Model weights are not included: download once in Settings or import a verified model offline. "
             "Application code, playback, CPU/media tools and help are inside the core installer.\n\n"
             "Read USER_GUIDE.md for use, README.md for source/development instructions, "
             "and THIRD_PARTY.md for redistribution obligations. The source ZIP contains only project sources.\n\n"
             "SHA256SUMS records the files in this folder. Checksums detect changes; they are not a code-signing signature.\n")
    (output / "START_HERE.md").write_text(guide, encoding="utf-8")
    entries = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            entries.append(f"{digest}  {path.relative_to(output).as_posix()}")
    (output / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(f"Sharing folder: {output}")


if __name__ == "__main__":
    main()
