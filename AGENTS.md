# Subloom — MVP Coding Agent Instructions

> **Project:** Subloom, an open-source, privacy-first desktop subtitle generator.  
> **Deliverable:** A **working, polished MVP**, not a mockup, scaffolding-only repository, or professional video editor.  
> **Primary platform:** Windows 10/11 (64-bit).  
> **Primary use case:** Convert locally stored English, Hindi, and mixed Hinglish video/audio into synchronized subtitles, with Roman Hindi or English output.  
> **Source of truth:** This document defines mandatory MVP scope. Later-release ideas are **not** part of the implementation request.

## 0. Instructions for the coding agent

1. Read this entire file and inspect the existing repository, dependencies, and tests before modifying anything. **Preserve existing working code**; refactor only when needed.
2. **Implement the complete MVP described here**. You may divide work into internal tasks and commits, but do **not** stop after building the UI, importing a file, or generating an SRT. Deliver the entire MVP and its tests without requiring approval at every step.
3. Favor **simple, maintainable, production-quality implementations** over additional frameworks, speculative abstractions, or unnecessary feature breadth. Keep UI, media, speech engine, text transformation, and exports separately testable.
4. Do not create fake functionality: no placeholder playback, hardcoded transcripts, simulated downloads, invented speed/accuracy percentages, fake GPU acceleration, or decorative buttons pretending to work.
5. Make **local privacy the default**. Never upload user media, transcripts, subtitle text, or file metadata. No cloud AI/API dependency or telemetry. The only permitted network operation is an explicit, user-authorized download of an AI model or required installation asset.
6. Do not silently compromise quality. Preserve original media, transcript results, and timestamps. Lower resource usage must not silently replace a model the user explicitly selected with a worse one.
7. Run tests, fix errors, and perform end-to-end checks. Do not claim an untested capability is verified. If Windows, CUDA, or other required hardware is unavailable in the agent's environment, implement a real path and document the exact steps to test it; disclose the verification gap.
8. Do not implement the future-phase features listed at the end unless absolutely necessary to make MVP functionality reliable.
9. Use safe subprocess argument arrays; never interpolate untrusted filenames into shell command strings. Handle Unicode filenames, spaces, missing dependencies, errors, and cancellation.
10. Respect third-party licenses, model redistribution terms, and Windows packaging requirements. Do not assume every binary/model can legally be bundled.

## 1. Product definition and boundaries

**Subloom MVP = import one local video/audio file → choose subtitle output and AI model → download the model once if needed → transcribe locally → preview and edit captions → export subtitle files or a captioned MP4.**

### Must-have user promises

- Runs on **CPU-only computers**, including reasonably constrained Windows laptops. A compatible NVIDIA GPU **may** speed up inference but must never be required for core functionality.
- All transcription and translation inference happens **on the user's machine**, including when an internet connection is available.
- User understands the model's **relative speed, expected accuracy tier, download size, and compatibility** before choosing it.
- Supports **English, Hindi, and mixed Hinglish speech**; generates both readable Roman-Hindi mixed text and English translation.
- Broad media input through FFmpeg; original video/audio remains **untouched**.
- Polished, intuitive, responsive desktop interface with working playback and usable subtitle editing.
- Basic subtitle/text exports **and** a video with permanently burned-in captions.

### Out of scope for MVP

Do **not** spend MVP effort on waveform editing, drag-to-trim timeline, batch processing, speaker diarization, animated karaoke effects, advanced subtitle styling/presets, multiple ASR engines, model-to-model accuracy leaderboards, cloud accounts, collaboration, plugins, online video downloading, complex project databases, or macOS/Linux installers.

A single-file workflow and one excellent AI backend are enough for MVP.

## 2. MVP feature contract

### 2.1 Media import

- Accept files via **drag-and-drop** and **Open File** dialog.
- Video targets: `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.m4v`, and other formats supported by the shipped FFmpeg build.
- Audio targets: `.mp3`, `.wav`, `.flac`, `.m4a`, `.aac`, `.ogg`, `.opus`, and other formats supported by the shipped FFmpeg build.
- Use **FFprobe** to inspect actual media/container codecs, duration, available audio tracks, sample rate, and streams. Do not assume extensions imply valid media.
- If multiple audio tracks exist, let the user choose which one to transcribe; default to the primary/default audio track.
- Display filename, duration, detected media type, and helpful errors for corrupt/unsupported files or files without audio.
- For ASR, extract/decode selected audio to a temporary 16 kHz mono PCM WAV or equivalent Whisper-compatible representation, without altering original media. Clean up temporary files safely.
- Handle long files without loading the whole video into application memory; apply chunking **only if needed**, with correct timestamp offsets and boundary handling.

### 2.2 Subtitle language/output modes

Offer the following clearly labeled choices:

1. **Hinglish (Roman Hindi)** — Preserve spoken English in English; represent Hindi words in readable Latin spelling. Example input: `आज हम neural networks समझेंगे` → `Aaj hum neural networks samjhenge`.
2. **English translation** — Render Hindi speech into natural English and retain existing English terminology. Example: `आज हम neural networks समझेंगे` → `Today we'll understand neural networks.`
3. **Original transcription** — Show the original recognized text/scripts without an extra translation/transliteration layer (a minimal, useful option).

Implementation rules:

- Use the same selected **multilingual** Whisper model for initial ASR. **Never use `.en` models** for Hindi/Hinglish recordings.
- Keep the raw recognized segments and timestamps separate from user-edited and transformed versions. Never overwrite the raw transcript.
- Romanization must operate on identified Devanagari Hindi spans while leaving Latin-script English and technical vocabulary unchanged. Use a lightweight local transliteration implementation/library plus readable normalization rules; don't add a multi-gigabyte LLM merely to transliterate.
- If Hindi is already recognized in Latin characters, do not destructively re-transliterate it; preserve it and allow correction. Do not assume perfect word-level language identification.
- For MVP English mode, run **Whisper's local audio-to-English translation mode**, using the existing compatible multilingual model. It may need a second inference pass. Translation is **not** performed by sending text to any remote service.
- Recognize limitations: transcription/translation of rapid code-switching may be imperfect. Provide a functional editor for corrections rather than falsely guaranteeing accuracy.
- Cache the output of an already completed mode for the current file + model/settings; switching to a previously completed mode must not rerun ASR unnecessarily.
- Preserve segment-level timestamps for both original and translated output, while allowing user correction of timings. Translation changes word length and must not be treated as word-aligned.

### 2.3 AI inference — one backend for MVP

**Primary engine:** [`ggml-org/whisper.cpp`](https://github.com/ggml-org/whisper.cpp), running **locally** via a clearly isolated adapter. Use the current `whisper-cli` interface (verify its options against pinned version instead of guessing).

**Supported initial models:** multilingual **Base**, **Small**, and **Medium** in formats compatible with the chosen whisper.cpp build. Allow compatible verified quantized variants when advantageous.

- **Base:** Lightweight / relatively fast; expected recognition trade-off.
- **Small:** Balanced starting point; default recommendation **when hardware permits**.
- **Medium:** Higher-quality option, but slower and more memory-hungry.
- A low-memory/CPU-only device may default to Base; do not claim that all three models will work with every RAM/VRAM configuration.
- Make CUDA GPU support available **only when a compatible Windows GPU build and drivers are present and validated**. CPU must work without CUDA, a dedicated GPU, or internet.
- If GPU execution fails, explain the error and **ask for confirmation** to retry on CPU (or use CPU when user selected Auto); do not silently change an explicitly selected GPU preference.
- Use a bounded thread count and one inference job at a time. No simultaneous loading of large model copies.
- Keep inference in a worker process or another nonblocking mechanism so the app remains usable while a model runs. Cancellation must actually terminate the work safely.
- Do not enable lossy/speed-up tricks that materially distort speech by default; optimize via inference backend, correct audio preprocessing, conservative threading, caching, and appropriate precision.

### 2.4 User-friendly model manager

On first use, show the three model options with:

- Friendly name (**Lightweight / Balanced / Higher Accuracy**) plus real model ID (**Whisper Base / Small / Medium**).
- **Approximate downloaded bytes** obtained from a trusted model manifest; actual model format/quantization must be identified.
- **Relative** speed and accuracy descriptions (not fabricated measurements like `97% accurate`).
- Hardware compatibility status: **Recommended / May be slow / Not enough memory or unsupported backend**, with a reason.
- **Installed / Download / Downloading / Ready / Failed** status.

Model download rules:

- Download from a pinned, trusted source **only on explicit user action**. Provide progress, cancellation, retry, hash/size verification when a checksum is available, and atomic finalization.
- Store locally under `%LOCALAPPDATA%/Subloom/models` by default; allow selecting a different model directory in Settings or the model manager.
- Detect existing installations; don't download the same model repeatedly. Permit deleting a model and re-downloading it.
- After a model exists on disk, transcription must run with **network fully disconnected**. The app must not unexpectedly phone home at startup.
- Display clearly: **“Models download to this computer. Your video/audio never leaves this device.”**
- Do not bundle every model with the app installer. Document a manual/offline model import route for computers without network access.

### 2.5 Intuitive hardware/performance options

Offer two simple selectors:

- **Accuracy/model:** Base / Small / Medium, with friendly labels and trade-offs.
- **Resource usage:** **Eco / Balanced / Performance**.

And one optional hardware selector: **Auto / CPU / GPU**.

Profile behavior:

| Profile | Intended behavior |
|---|---|
| Eco | Conservative CPU/thread use and batch size; responsive system even when slow. |
| Balanced | Default: moderate resources and sensible decoding. |
| Performance | Use more CPU resources or a validated GPU backend when available. |

**Resource profiles do not automatically swap out an explicitly chosen ASR model.** If the current device lacks sufficient memory, show a warning and suggest a different model with user confirmation.

- Auto-detect CPU/RAM and available supported GPU backend; do not assume a detected NVIDIA card is automatically compatible with the shipped CUDA build.
- Show whether a device selection is supported and why. A CPU-only fallback is mandatory.
- Show a general **speed tier** before download. An optional single-model local benchmark (e.g., short sample, not mandatory for generating subtitles) may show **estimated processing time** based on measured real-time factor. Label estimates, display uncertainty, and never invent benchmarks.
- Retain selected settings across app launches.

### 2.6 Desktop user interface

**Recommended UI:** Python **PySide6 + Qt Quick/QML**, dark theme, restrained blue accents, fluid resizable layout, readable typography, keyboard accessibility. Prefer native Qt components over Electron or embedding a browser.

**Playback:** use **libmpv** if an embedded Qt/QML integration is tested and maintainable; a genuine Qt Multimedia playback implementation is an acceptable MVP fallback if reliable on Windows. Use FFmpeg to handle media preprocessing/transcoding when necessary. Do not show a fake video preview.

UI flow and screen content:

1. **Welcome/import:** Drag-and-drop area and Open File action; clear indication that processing is local.
2. **Configuration:** Selected media summary; output mode; friendly Base/Small/Medium model choices; download status; Eco/Balanced/Performance; Auto/CPU/GPU; Generate button.
3. **Processing:** Real current step (preparing audio / loading model / transcribing / translating / finishing); progress if measurable, elapsed time, Cancel. Never fake percent values.
4. **Editor:** Play/pause, seek, current time, video preview (or audio playback), on-screen subtitle preview, a scrollable **list of timestamped subtitle segments**.
5. **Export:** SRT / VTT / TXT and MP4 with burned-in captions; clear progress and final output location.

Minimum editing behavior:

- Click segment to jump playback to its timestamp.
- Edit segment text, start time, and end time; validate `0 <= start < end <= duration` where duration is known.
- Add or remove a segment, if needed to correct output.
- Keep caption overlay in sync with playback while editing.
- Save current edited transcript for the imported file in a simple local session JSON so an accidental app restart doesn't destroy work. This is **not** a full multi-project workspace.
- At least one clear Export action; sensible busy/disabled states and accessible dialogs.

Performance rules:

- No heavy computation on UI thread, no large synchronous file reads in QML, and no repainting huge lists every frame.
- Avoid heavy animations, web-based UI layers, unnecessary graphics effects, and displaying all subtitle rows if virtualized models can be used.
- Support typical laptop window sizes and Windows scaling (100–200%).

### 2.7 Export and preservation of media quality

**Mandatory exports:**

- `.srt`: correctly numbered cues, UTF-8, valid `HH:MM:SS,mmm` timings.
- `.vtt`: valid `WEBVTT` header and timestamps.
- `.txt`: human-readable transcript, with an option to include timestamps if trivial.
- `.mp4`: captioned video with subtitles **burned into the picture** using FFmpeg's libass-capable subtitle filter.

Rules:

- Exported SRT/VTT/TXT must reflect the **edited** captions in the selected output mode.
- For video import, retain source video resolution and frame rate by default; preserve original audio by stream-copy when output compatibility permits. Burning subtitles requires video re-encoding — do not claim it is lossless.
- Use a reasonable high-quality H.264 output preset (with documented adjustable quality control only if simple); never silently reduce output dimensions, bitrate or frame rate to speed up processing.
- Audio-only files: disable MP4 video export or explain clearly that a video source is required. Do not silently fabricate blank videos.
- Do not overwrite source files, ever. Use a separate destination and handle existing output files safely.
- Display and test proper Windows path escaping for FFmpeg/libass filters, including drive letters, Unicode and spaces.
- Ensure export cancellation and failed encode cleanup work predictably.

## 3. Recommended minimal architecture

Do **not** overengineer. Use an uncomplicated structure such as:

```text
subloom/
├── AGENTS.md                   # identical copy of this file for compatible agents
├── README.md                   # setup, use, offline guarantee
├── pyproject.toml              # pinned runtime/dev dependencies
├── src/subloom/
│   ├── __main__.py             # launch app
│   ├── app.py                  # app composition and state
│   ├── ui/                     # Qt Quick/QML + thin Python bridges
│   ├── media.py                # FFprobe, FFmpeg, temp audio, export
│   ├── player.py               # actual playable media integration
│   ├── whisper_engine.py       # one whisper.cpp wrapper
│   ├── models.py               # manifest, download, verify, local paths
│   ├── hardware.py             # CPU/RAM/GPU detection + safe presets
│   ├── language.py             # romanization, output mode conversion
│   ├── subtitles.py            # segments, SRT/VTT/TXT, editing validation
│   ├── session.py              # lightweight JSON autosave/cache
│   └── workers.py              # cancellable nonblocking jobs
├── tests/
│   ├── fixtures/              # tiny licensed/generated English/Hindi test clips
│   └── test_*.py
└── packaging/                  # Windows build spec and scripts
```

Folder structure may be adapted to an existing repository; the **separation of responsibilities** is mandatory, not the exact filenames.

### Segment schema

Use one consistent, validated internal representation, for example:

```python
@dataclass
class SubtitleSegment:
    id: str
    start_ms: int
    end_ms: int
    text: str
```

Keep raw ASR segments, mode-specific generated segments, and user edits as distinct data snapshots. Store mode, engine/model ID, source identity (path + safe fingerprint/metadata), settings, and cache version in the session JSON; invalidate caches when source/model/settings change. Never rely only on filename as cache identity.

### End-to-end pipeline

```text
User imports local file
    -> FFprobe validates media and chooses audio stream
    -> FFmpeg decodes selected audio for ASR (temporary file)
    -> whisper.cpp transcribes with local multilingual model
    -> save raw segments + timestamps
    -> selected mode:
         * Original: unchanged transcript
         * Hinglish: Devanagari -> readable Roman Hindi (keep English)
         * English: local Whisper audio-to-English pass (cached)
    -> display synchronized editable segments + playback
    -> SRT / VTT / TXT export OR FFmpeg burned-caption MP4
```

## 4. Engineering standards

- Target a supported Python 3 version and **pin compatible package versions**. Avoid requiring full PyTorch simply to run whisper.cpp inference.
- Use explicit type hints for core logic, dataclasses or simple typed models, pathlib, structured errors, and small modules.
- Use subprocess APIs with argument lists and tightly controlled executable locations; quote/escape subtitle filter paths correctly.
- Generate temporary files under a managed cache directory; clean up after failure or cancellation. Do not log personal transcript content.
- Provide clear messages for missing FFmpeg/libass, incompatible GPU backend, missing model, checksum mismatch, insufficient disk space, permission errors, broken media, and no speech detected.
- Keep dependency installation simple. Never require a paid API key or third-party hosted account.
- Provide a deterministic model manifest (model ID, supported languages, source URI, expected size, optional/checkable SHA-256, compatible quantization/backend). Verify manifest entries; don't guess hardcoded hashes.
- Document sources and licenses for whisper.cpp, model weights, FFmpeg, libmpv/Qt dependencies and bundled binaries. Choose a compatible license for Subloom after auditing dependencies.
- Include `.gitignore` entries for models, original media, generated media, transcript caches, build output, and environment files. No user data committed to Git.

## 5. Testing and definition of done

The MVP is complete **only when all mandatory rows pass**, or a blocked hardware/OS-specific test is explicitly reported as **not verified** with reproduction steps. No placeholder implementation counts as a pass.

### Test categories

| Area | Minimum verifiable test |
|---|---|
| Import | Valid MP4, MKV, MOV, MP3, WAV, FLAC; corrupt file; missing audio; unusual/Unicode path; more than one audio stream. |
| ASR | Actual Whisper model transcribes a real English sample, Hindi sample, and Hinglish code-switching sample **locally**, with valid timecoded segments. |
| Romanization | Devanagari converts to readable Roman Hindi; English segments and technical terms remain unchanged; existing Latin-script Hinglish is not destroyed. |
| Translation | A mixed-language sample produces an actual local English translation; proper timestamps and editable output. Review obvious translation failures on the test set. |
| Model manager | Download, hash/size validation where possible, cancel/retry, local reuse, deletion, and manual installation; no media upload. |
| Offline | After installing the model, disconnect networking: import → transcribe → edit → export still works. |
| CPU | Complete end-to-end ASR on a CPU-only configuration (real or documented CI/VM environment). |
| GPU | Where compatible hardware is available, complete a real NVIDIA GPU inference run; otherwise mark specifically unverified, not implemented/verified by assumption. |
| UI | Preview playback, seek, segment synchronization, text/timestamp editing, working cancel, no frozen UI. |
| Subtitle export | Parse exported SRT/VTT back and verify edited text and timestamps; valid TXT export. |
| Video export | Export a captioned MP4, verify that subtitles are visible, source video resolution is retained, sound exists, and input file hash is unchanged. |
| Windows release | Clean Windows machine/VM can install/run without Python installed, subject to documented system prerequisites. |
| Error handling | Missing model, missing FFmpeg/libass, network failure during a model download, unsupported video, low disk space, subprocess failure. |

### Quality acceptance

- Test on a small, legally usable **English/Hindi/Hinglish** corpus with reference transcripts. Record basic accuracy observations and code-switching errors; don't use an unearned numeric accuracy claim.
- Ensure there is a usable path to manually correct ASR mistakes. Optimization is **not** synonymous with choosing the smallest model.
- Use model speed labels as qualitative guidance until measured. If measured, specify the device/model/backend and distinguish the measured sample from an estimate for full-video runtime.
- Respect original source files: compare hashes before/after key operations; never modify them in place.
- UI must remain responsive while transcribing or exporting and during cancellation.

## 6. MVP completion deliverables

At final handoff, provide:

1. A working repository with actual import, playback, local inference, all output modes, model management, editing, and exports.
2. `README.md` with Windows installation, prerequisites, running from source, model downloading, offline use, limitations, and troubleshooting.
3. A reproducible Windows packaging command/script and, if the environment supports Windows builds, the installer/executable or packaged application.
4. Automated tests and the commands to run them; actual results, including E2E sample checks.
5. A concise implementation summary and **truthful** list of things not verified due to specific platform/hardware/environment limitations.

**Do not stop at a prototype. Do not add future-phase functionality just to make the project appear larger. Deliver the simple end-to-end MVP first.**

## 7. Roadmap — explicitly NOT required for MVP

### v1.0 — Polished editing workflow

Waveform timeline, drag-adjustable subtitle boundaries, split/merge shortcuts, undo/redo, advanced ASS styling, custom vocabulary/glossary, multiple saved projects, importing existing subtitle files, smarter GPU/CPU benchmarks.

### v2.0 — Automation and intelligence

Batch processing, speaker identification, selective retranscription, enhanced translation options, confidence-based suggestions, more Indian languages, optional additional local ASR backends.

### Future

Mac/Linux installers, public extension/plugin APIs, karaoke captions, editor integrations, collaborative workflows.

---

## 8. Official implementation references

- whisper.cpp main repository: https://github.com/ggml-org/whisper.cpp
- whisper.cpp CLI flags and local translation: https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/README.md
- whisper.cpp models: https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md
- FFmpeg user documentation: https://ffmpeg.org/ffmpeg.html
- FFprobe documentation: https://ffmpeg.org/ffprobe.html
- libmpv embedding options: https://github.com/mpv-player/mpv-examples/tree/master/libmpv
- PySide6 / Qt Quick: https://doc.qt.io/qtforpython-6/

Always cross-check APIs and license compatibility against the actual versions selected for the build.
