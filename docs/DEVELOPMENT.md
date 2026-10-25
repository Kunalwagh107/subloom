# Development and Windows builds

End users install the setup EXE. This document is for contributors and release builders.

## Environment

Use a supported 64-bit Python 3.11–3.13 environment (3.12 recommended).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python scripts/bootstrap_runtime.py --download
.\.venv\Scripts\python -m subloom
```

The explicit bootstrap command installs pinned Windows CPU/media assets under
`.tools/runtime`; it never downloads model weights. For GPU builds add `--gpu`.
For offline bootstrapping use `--archives PATH` containing the pinned `whisper.zip`
and `ffmpeg.zip`; `--gpu-archive PATH` supplies the optional pinned CUDA ZIP.

Download/import models explicitly in the app. Tests never fetch them automatically.
Do not add cloud inference, telemetry, paid API dependencies or media-upload code.

## Verification

```powershell
.\.venv\Scripts\python -m ruff check src tests scripts
.\.venv\Scripts\python -m pytest -q --basetemp=.test-data/pytest
```

Unit/media/UI checks run with available local dependencies. ASR tests skip unless
models and legally usable fixtures are installed. GPU execution is opt-in:

```powershell
$env:SUBLOOM_TEST_MODELS='PATH\TO\MODELS'
$env:SUBLOOM_TEST_CORPUS='PATH\TO\FIXTURES'
$env:SUBLOOM_TEST_GPU='1'
.\.venv\Scripts\python -m pytest -q --basetemp=.test-data/pytest
```

Fixtures use `english.wav`, `hindi.wav`, `hinglish.wav`. Original reference text
and a local eSpeak NG generator are in `scripts/make_speech_fixtures.py`:

```powershell
.\.venv\Scripts\python scripts/make_speech_fixtures.py --espeak PATH\espeak-ng.exe
```

Synthetic clips test implementation paths. They do not substitute for a Hindi
speaker's review of natural mixed-language recordings. Record skipped tests and
verification gaps rather than counting skipped model/hardware checks as passes.

GitHub Actions runs the Windows checks and the offline Docker backend checks on
pinned runner images. Push a change or use **Actions → Checks → Run workflow**.
Both jobs upload JUnit reports, including when tests fail. Windows uses the
runner's temporary directory; local nested `--basetemp` paths also work on a
fresh checkout because the test configuration creates their missing parents.

## Build a Windows release

Windows packaging must run on Windows. Install Inno Setup 6.7.3, make `ISCC.exe`
available on PATH or set `ISCC_PATH`, and comply with its compiler license.

```powershell
.\packaging\build.ps1 -Installer
.\.venv\Scripts\python scripts/package_release.py
```

The build script uses `.venv` when available or Python on PATH. Use `-Python PATH`
for another prepared environment. It reads the version from `subloom.__version__`;
Python package metadata and both installer names use that same source.

- `dist/portable/<version>/Subloom/`: portable application; keep the whole folder together.
- `dist/installers/`: core setup and optional GPU add-on when its runtime is present.
- `dist/share/`: installers, source ZIP, user guide, notices and SHA-256 checksums.

The installers include documentation and licenses. Models, settings, sessions,
media, dev environments and compiler downloads are excluded. The optional GPU
runtime is separate to keep CPU-only installations smaller. Do not remove Qt
libraries required for playback, fonts, Basic controls or software rendering.

`scripts/check_installers.ps1` installs into a guarded workspace test folder,
checks a frozen application launch, then uninstalls those test copies. It refuses
to replace a registered user installation outside that area. It is not a clean-VM
or code-signing check. The script expects both installers to be built.

## Configuration overrides

Normal users need none. Advanced/test setups can set:

| Variable | Purpose |
|---|---|
| `SUBLOOM_DATA_DIR` | Local settings/session/model root |
| `SUBLOOM_TOOLS_DIR` | Trusted runtime executable directory |
| `SUBLOOM_FFMPEG`, `SUBLOOM_FFPROBE`, `SUBLOOM_WHISPER_CLI` | Trusted absolute executable paths |
| `SUBLOOM_GPU_CLI` | Separate compatible CUDA whisper-cli path |
| `ISCC_PATH` | Windows installer compiler |

Windows defaults use LocalAppData. Headless Unix testing honors `XDG_DATA_HOME`.
No username, drive letter or GPU model is used to select inference behavior.

## Cleanup

```powershell
.\scripts\clean.ps1 -IncludeDownloads -IncludeTestRuns -BuildOutput
# Inspect the preview, then add -Apply to remove the listed generated artifacts.
```

The cleanup preserves source, the development environment, runtime/installer
tools, installed test models, baseline fixtures and finished release artifacts.
It validates project-relative targets and refuses linked cleanup directories.
Source ZIP generation uses an allow-list and excludes private/runtime artifacts.

See [Docker testing](DOCKER.md) for a headless CPU development container. The GUI,
Windows installers and optional Windows CUDA package are not Docker services.
