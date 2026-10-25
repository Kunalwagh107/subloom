# Docker: headless backend tests

Docker is optional contributor tooling. It is **not** needed by Windows users and
does not provide the desktop GUI or produce Windows installers.

The image uses an official pinned Python base, builds CPU-only whisper.cpp from
an exact commit with a verified source-archive SHA-256, and installs FFmpeg plus
headless Qt dependencies. Native-host CPU tuning is disabled. Tests run as an
unprivileged user, with networking disabled and a temporary writable filesystem.
The image does not contain models, recordings or a CUDA runtime.

## Run

Install Docker with Linux-container support, then from the repository root:

```sh
docker compose build tests
docker compose run --rm tests
```

Building the image downloads installation dependencies. Running its default
test command has no network access. The `.dockerignore` allow-list excludes
environments, `.tools`, `.test-data`, model weights, media, sessions, secrets and
release binaries from the build context.

The default selection runs core/media/downloader/cache/backend unit checks. GUI
and actual-ASR tests are excluded. Model-dependent checks never download weights.

## Optional actual CPU ASR

Prepare verified multilingual models and licensed fixtures on your host first.
Use absolute host paths for the two **read-only** mounts:

```sh
docker run --rm --network none \
  --mount type=bind,source=/absolute/models,target=/models,readonly \
  --mount type=bind,source=/absolute/fixtures,target=/fixtures,readonly \
  -e SUBLOOM_TEST_MODELS=/models \
  -e SUBLOOM_TEST_CORPUS=/fixtures \
  subloom-backend-tests:local \
  python -m pytest -q tests/test_asr.py \
  --basetemp=/tmp/subloom-asr -o cache_dir=/tmp/pytest-cache
```

For PowerShell, use absolute Windows paths for mount sources and put the command
on one line or use PowerShell continuation syntax. The fixture folder needs
`english.wav`, `hindi.wav` and `hinglish.wav`. Base is the default test model;
`SUBLOOM_TEST_MODEL=small` selects an explicitly installed Small model.

This CPU image favors a portable test build over host-specific speed. Do not use
its runtime as a desktop performance benchmark. Windows playback, installer,
display-scaling and GPU checks still run on actual compatible Windows hardware.

## Verification status

Docker configuration is checked in and CI is configured to build/run it on Linux. The Docker
image was **not executed in the current authoring environment**, where Docker
is unavailable. A successful local Windows test run is not Docker verification.
Run the commands above, or inspect CI after publishing the repository, before
advertising container support as verified.
