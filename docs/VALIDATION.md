# Validation and release status

Subloom has real local media, inference, playback, editing and export paths. Tests
must distinguish implementation checks from natural-speech quality and hardware
coverage. A passing unit test is not a universal compatibility or accuracy claim.

## Local release check — 0.2.1

On 2026-10-25, the complete Windows suite passed: **56 passed in 126.98 seconds**,
with `SUBLOOM_TEST_GPU=1`, verified local Base/Small weights and generated
English/Hindi/Hinglish fixtures. This exercised real CPU inference, CUDA inference,
translation, desktop playback/editing and all export formats. Ruff passed and the
Python wheel built with the expected version and QML/model-manifest resources.

Both Windows installers installed into an isolated test directory. The installed
0.2.1 application loaded QML and its bundled CPU/media tools, detected the separate
GPU runtime, and exited successfully; both test installations then uninstalled.
This is a check on one development host, **not** clean-machine certification.
Docker, natural-speech accuracy and the other limits below remain unverified.

## Automated coverage

The suite covers:

- Real FFprobe/FFmpeg import for MP4, MKV, MOV, MP3, WAV and FLAC; corrupt/no-audio
  input; multiple tracks; spaces, Unicode and unusual filenames.
- 16 kHz mono PCM preparation, valid segment timestamps, independent raw/generated/
  edited snapshots, source fingerprints, mode caching and session recovery.
- Romanization of Devanagari spans without changing Latin English text.
- Actual multilingual Whisper CPU recognition and local translation when explicitly
  supplied models and English/Hindi/Hinglish fixtures are available.
- Optional actual CUDA inference and process cancellation on a compatible host.
- Auto/CPU/GPU behavior, confirmation semantics for explicit GPU errors, conservative
  thread limits and model preservation across resource profiles.
- Model/runtime download verification, cancellation, reuse, offline import, deletion,
  network failure, low disk space and staged-file cleanup.
- SRT/VTT round trips with an independent parser, TXT, actual visible libass burn-in,
  retained video dimensions/frame timestamps/audio, and unchanged source hashes.
- Real Qt playback frames/seek, editing, autosave/restart, repeated background jobs,
  responsive cancellation, dark popups and resizable logical layouts.
- Source-release exclusions and portable configuration behavior.

Tests never download models. Missing optional fixtures, models or hardware cause
explicit skips and must not be reported as successful ASR/GPU verification.

## Run locally

Follow DEVELOPMENT.md, then run:

```powershell
.\.venv\Scripts\python -m ruff check src tests scripts
.\.venv\Scripts\python -m pytest -q --basetemp=.test-data/pytest
```

For real ASR provide verified model files and a legally usable fixture directory
with `english.wav`, `hindi.wav`, `hinglish.wav`. Configure `SUBLOOM_TEST_MODELS` and
`SUBLOOM_TEST_CORPUS`; enable `SUBLOOM_TEST_GPU=1` only for an available compatible
CUDA runtime. The eSpeak NG fixture generator is included for repeatable local
engineering checks. Synthetic speech does not establish natural voice accuracy.

## Windows distribution checks

The Windows build includes the application, Qt/Python, CPU inference/media tools,
documentation and license files. Models and the optional GPU component are separate.
`--smoke-test PATH` checks QML load, frozen-runtime status, bundled tools and optional
GPU-runtime detection, and writes a local report plus a window capture.

`scripts/check_installers.ps1` can install both setup packages in a guarded
workspace directory, launch the installed application with an isolated profile,
then uninstall only those copies. It refuses to replace a registered user
installation outside the test area. This host test is not a clean-VM check.

## Verification limits

- CPU and NVIDIA execution have been exercised locally, but not every supported
  CPU, graphics family, driver, memory budget or Windows version has been tested.
- A clean Windows VM without Python, with only documented prerequisites, still
  needs a full install/import/play/edit/export acceptance run before public release.
- Logical-size layout tests do not replace physical 100–200% display-scaling checks.
- Docker cannot be executed in the current authoring environment because its CLI/
  daemon is unavailable. The Dockerfile and CI path are supplied; see DOCKER.md.
- Physical network-adapter disconnection and connection monitoring remain manual
  release checks. Local inference has been run with network requests prohibited.
- Natural Hindi/Hinglish recordings, noisy/rapid code-switching, silence, names and
  long-form chunk boundaries need native-speaker review. Synthetic samples exposed
  substitutions, unexpected scripts and translation errors; these are not hidden.
- Full multi-hour processing time, boundary fidelity and constrained-memory behavior
  require representative long recordings. No guaranteed runtime is advertised.
- Public code signing and third-party corresponding-source delivery remain release
  responsibilities; see THIRD_PARTY.md.

Original media must remain untouched in every acceptance run. Review recognition
and translation manually; keep raw results separate from corrections. Add concrete
OS/backend/model observations when publishing release test results, without
committing private transcripts, local user paths or personal recordings.
