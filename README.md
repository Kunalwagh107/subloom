# Subloom

**Private subtitles. Local AI. Your media stays on your computer.**

Subloom is an open-source desktop subtitle generator for English, Hindi and mixed
Hinglish recordings. Open one local video or audio file, generate captions, review
and edit them alongside real playback, then export subtitles or a captioned video.

Built for **Windows 10/11, 64-bit**. CPU processing is supported; a compatible NVIDIA
GPU is optional. No account, API key, cloud inference or subscription is required.

## Install

1. Get `Subloom-Setup-<version>.exe` from the project's release or shared release folder.
2. Run the installer, then open **Subloom** from the Start menu. **Python, a venv and
   Docker are not needed.**
3. Open **Models & settings**, choose a multilingual model and press **Download**.
   You can import a verified model from another computer for an offline installation.

For optional NVIDIA acceleration, run `Subloom-NVIDIA-Setup-<version>.exe` and
restart Subloom, or choose **Enable NVIDIA acceleration** in the app. Keep your
NVIDIA driver up to date. CPU processing remains available when CUDA is unavailable.

The Windows binaries require the [Microsoft Visual C++ x64 runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
If Windows reports a missing `MSVCP140` or `VCRUNTIME140` DLL, install that prerequisite.
The current builds are unsigned; code signing and clean-machine release validation
are still pending.

### What is inside the installer?

| Component | Included? |
|---|---|
| Desktop interface, editor, playback and application code | Yes |
| Python runtime and pinned Qt/PySide6 libraries | Yes; no separate Python installation |
| CPU whisper.cpp, FFmpeg and FFprobe | Yes |
| User guide, troubleshooting and third-party license notices | Yes |
| AI model weights | No; download once or import locally |
| CUDA libraries | Separate optional NVIDIA add-on |
| NVIDIA driver / Microsoft system prerequisites | Installed separately when needed |
| Your recordings, transcripts, settings or development tools | Never bundled |

A **setup EXE** installs the complete application. For a portable build, keep the
**entire `Subloom` folder** together: copying only `Subloom.exe` from that folder
will not include its accompanying libraries.

## Make subtitles

1. **Import** one local recording with Open recording or drag-and-drop. For files
   with multiple audio tracks, choose a track in Settings; playback follows it too.
2. **Choose output:** Roman Hindi, English translation or original transcription.
3. **Choose a model and compute profile**, then generate. Progress, elapsed time,
   cancellation and current processing steps are real.
4. **Review:** play, pause and seek; click a caption to jump to it. Edit text and
   start/end times, or add/remove captions. Changes autosave locally.
5. **Export:** SRT, VTT, TXT, or an MP4 with captions burned into the video.

| Output | Behavior |
|---|---|
| Hinglish (Roman Hindi) | Converts recognized Devanagari spans to readable Latin spelling; existing Latin text is kept |
| English translation | Uses the selected multilingual model's local audio-to-English mode; normally requires a second inference pass |
| Original transcription | Keeps recognized text in its original script |

For example, Hindi speech mixed with “neural networks” can be presented as
`aaj hum neural networks samjhenge`. Recognition and spelling can be imperfect:
review names, technical terms, code-switching and translations before sharing.

Keyboard shortcuts: **Ctrl+O** open, **Ctrl+Enter** generate, **Ctrl+Space** play/pause.
Edit timestamps using `HH:MM:SS.mmm`. **Help / F1** opens the built-in quick-start panel.

## Choose a model

All supported models are **multilingual GGML F16** models for the pinned whisper.cpp
backend. English-only `.en` models are not accepted.

| Model | Approximate download | Best fit | Trade-off |
|---|---:|---|---|
| Base | 148 MB | Quick drafts and constrained computers | More recognition mistakes, especially in mixed speech |
| Small | 488 MB | Recommended starting point when memory allows | More processing time than Base |
| Medium | 1.53 GB | More detailed recognition on capable systems | Substantially more memory and time |

The app estimates compatibility using **the current device's available resources**.
It is not tied to a particular GPU model or computer. Approximate free-memory
budgets are 1.5 / 3 / 6 GB for Base / Small / Medium, with headroom; these are
conservative guidance rather than guarantees.

**Eco**, **Balanced** and **Performance** control bounded CPU resource use.
**Auto** attempts an available NVIDIA backend in Balanced or Performance; Eco
stays on CPU. An explicit GPU failure asks before a CPU retry. Profiles never
silently replace your chosen model.

**Fast decoding** is optional and off by default. It checks fewer candidates,
which can reduce accuracy, while retaining your chosen model. Processing speed
varies with hardware, audio and settings; no universal speed or accuracy claim is
made. See [performance and long recordings](docs/PERFORMANCE.md).

## Privacy and offline use

> Models download to this computer. Your video/audio never leaves this device.

Transcription, translation, romanization, playback, editing and exports happen
locally. The app has no telemetry, account service, automatic update checks, or
cloud AI calls. Network code is used only after an explicit model-download or
optional-runtime installation action. Trusted downloads use pinned sources and
size/hash checks before installation.

Once the runtime and model are installed, you can disconnect networking. Online
video URLs are not supported. Use genuinely local files for an offline workflow;
remote filesystem shares and OS-managed cloud folders are outside the app's control.

Default Windows storage is `%LOCALAPPDATA%/Subloom`:

- `models/`: installed weights; choose another local folder in Settings.
- `settings.json`: preferences and the last opened recording path.
- `current.session.json`: source fingerprint, raw transcript, generated modes and edits.
- `previous.session.json`: one recovery snapshot when new results replace old ones.
- `cache/`: temporary processing files and the current resume checkpoint.
- `runtimes/gpu/`: optional NVIDIA support.

Sessions contain private text. They are ordinary local files, not encrypted storage.
Uninstalling the app preserves your models and saved work. Delete the data folder
yourself if you want to erase it. Never include it in a shared source archive.

## Quality and long recordings

The original recording is never overwritten. Subtitle exports reflect the selected
edited captions. MP4 export preserves source dimensions and frame timestamps by
default and stream-copies compatible selected audio; otherwise audio becomes AAC.
**Burning captions re-encodes video** with a high-quality H.264 preset; it is not
lossless. MP4 video export requires a video source.

Long recordings use bounded audio chunks. Completed chunks are checkpointed so
matching runs can resume after cancellation or restart. Completed output modes
are cached. Changing the source, model, audio track, language, decoding or backend
settings can invalidate a resume checkpoint. Estimates are labelled and apply to
the current inference pass. A three-hour recording can still take substantial time.

Whisper may hallucinate on silence, miss fast code-switching, return an unexpected
script, or translate terminology incorrectly. Romanization handles Devanagari;
it does not translate arbitrary other scripts. Raw results remain separate from
edits so corrections never overwrite the recognized transcript.

## Troubleshooting and help

- **First use / no model:** download or import one in Models & settings.
- **Slow processing:** check the reported backend, close competing applications,
  try Performance, or explicitly choose Fast decoding / Base with their quality trade-offs.
- **GPU unavailable:** install the optional runtime and a compatible driver, then
  restart. GPU detection alone does not guarantee CUDA compatibility. CPU still works.
- **Checksum failure:** delete the damaged model/runtime and download or import it again.
- **No speech / wrong language:** check the audio track and playback. Try selecting
  Hindi / Hinglish instead of Auto-detect for Hindi-heavy mixed recordings.
- **Export fails:** choose a new filename and check disk space and permissions.
  Existing files and source media are not overwritten.
- **Playback codec error:** use the documented runtime; remux or transcode a copy
  if Qt Multimedia cannot decode that source codec.

See the [user guide](docs/USER_GUIDE.md), [validation status](docs/VALIDATION.md) and
[third-party licenses](docs/THIRD_PARTY.md).

## Develop, test and build

The source targets Python 3.11–3.13, with pinned runtime/dev dependencies and
whisper.cpp as the single inference backend. Start with [development instructions](docs/DEVELOPMENT.md).
Docker provides **headless CPU backend tests**, not a replacement Windows desktop UI:

```sh
docker compose build tests
docker compose run --rm tests
```

The image build downloads installation dependencies and verifies the pinned
whisper.cpp source archive. The test container runs without networking. Models
and recordings are excluded from its build context and are never downloaded by tests.
See [Docker usage](docs/DOCKER.md) for optional local model/fixture mounts.

```text
src/subloom/  Local media, inference, transformations, sessions and Qt UI
tests/        Unit, media, optional actual-ASR and desktop integration checks
packaging/    Windows portable package and installer definitions
scripts/      Runtime bootstrap, sample generation, benchmark and release tooling
docs/         User, developer, Docker, validation and licensing documentation
```

## Sharing and contributing

For end users, share the setup EXE and optionally the NVIDIA add-on. The release
folder includes a short guide and checksums. Share source using the generated
source ZIP or your Git repository, not a copy of your entire development folder.
The source bundle excludes environments, models, user data, generated media,
compiled libraries, caches and installer/compiler downloads.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow. Keep issue reports and
screenshots free of private media paths, transcripts and session JSON.

## License

Subloom is **GPL-3.0-or-later**; see [LICENSE](LICENSE). Third-party binaries and
model weights have their own terms. Binary distributors must satisfy the applicable
notice and corresponding-source obligations described in [THIRD_PARTY.md](docs/THIRD_PARTY.md).
