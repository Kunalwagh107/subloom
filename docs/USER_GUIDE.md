# Subloom user guide

## Install and first run

Use the Windows setup EXE supplied with this release. It contains the desktop
application, Python/Qt runtime, CPU whisper.cpp, FFmpeg/FFprobe, documentation and
license notices. A separate Python installation or Docker is unnecessary.

Install the optional NVIDIA add-on only if you want compatible CUDA acceleration.
It contains runtime libraries, not a driver or model weights. Restart Subloom
after installing it. Alternatively, use the explicit NVIDIA download in Settings.
CPU processing remains available.

If Windows reports missing MSVCP/VCRUNTIME libraries, install the Microsoft Visual
C++ x64 runtime linked in README.md. These builds are unsigned. The application
targets Windows 10/11 x64; a GPU is optional.

## Models

Choose Base for a draft on constrained hardware, Small as the recommended starting
point with enough memory, or Medium when quality matters more than time/memory.
Model compatibility reflects the current machine's available resources.

Download starts only when you press Download. The app verifies the pinned file's
size and SHA-256 before installing it. For an offline computer, transfer the exact
multilingual GGML F16 model from the revision in `model_manifest.json`, select the
matching model in Settings, and choose Import offline model. `.en` and mismatched
files are rejected. You can change the local model folder and delete/reinstall models.

Models download to this computer. Your video/audio never leaves this device.

## Import, generate, review

1. Open or drop one local video/audio recording. FFprobe validates the actual
   streams, not just the filename extension. Choose an audio track if there is more than one.
2. Choose Roman Hindi, English translation, or Original. Romanization preserves
   existing Latin text and changes Devanagari spans. English translation normally
   runs a second local inference pass using the same multilingual model.
3. Choose a model, profile and device. Auto can attempt installed NVIDIA support
   in Balanced/Performance; Eco stays on CPU. Fast decoding is an explicit optional
   accuracy trade-off. Profiles do not replace the model you selected.
4. Generate and review the result. Processing stays in the background; Cancel
   terminates the work. The original recording is never modified.
5. Play or seek, click a cue to jump to it, edit its text and timings, or add/remove
   a cue. Times use `HH:MM:SS.mmm` and must stay within the recording duration.

Shortcuts: Ctrl+O opens a recording, Ctrl+Enter generates, Ctrl+Space plays/pauses.
Raw recognition is stored separately from generated modes and user edits.

## Export

SRT, VTT and TXT contain the edited captions. TXT can include times. Choose MP4
for a video source to burn captions into the picture. Video is re-encoded as
high-quality H.264 at source dimensions/frame timestamps; compatible selected
audio is copied, otherwise encoded to AAC. This is not lossless video editing.
Audio-only recordings export subtitle/text files rather than a fabricated video.

Choose a separate new destination. The app refuses to overwrite the original or
an existing output. Show export opens the destination folder.

## Long recordings and recovery

Completed audio chunks are checkpointed locally. Generate with matching source,
model, track, language, decoding/profile and backend settings to resume. Only an
interrupted chunk needs to repeat. Starting a different task can replace the single
current checkpoint. Finished output modes are cached with their edits.

The last recording and edits restore after restart if the source still matches.
Older completed captions can be shown while newer pending compute preferences
remain selected; Generate uses the selected settings. Export important work
before starting a different recording: this is a single-current-session app.

An estimate is based on measured progress for the current pass, not a guaranteed
processing time. Translation's second pass takes additional time.

## Local files and privacy

Windows data lives under `%LOCALAPPDATA%/Subloom`, unless explicitly overridden.
It includes models, settings, the current/previous session JSON, optional GPU
libraries and processing cache. Session files contain private text and file paths.
They are not encrypted. Uninstall preserves this data so upgrades do not erase work.
Delete it yourself to erase saved models/transcripts. Never distribute that folder.

Networking is used only for explicit model or optional-runtime installation.
After installation, import, inference, editing and export work locally. Do not
use a remote share or OS-managed cloud placeholder if you require a physically
offline workflow.

## Recognition limits

Fast code-switching, accents, noise, names, silence and technical terms can produce
errors. Hindi may be recognized in Latin or an unexpected script. Romanization
does not repair every ASR error or translate arbitrary scripts. Review translations
and correct captions in the editor; no accuracy percentage is promised.

For troubleshooting, performance guidance and verification limits, see README.md,
PERFORMANCE.md and VALIDATION.md in the supplied documentation folder.
