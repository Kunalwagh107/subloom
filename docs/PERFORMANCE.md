# Performance and long recordings

Subloom uses one local whisper.cpp backend. Performance settings are based on
available resources and the selected backend, never on a hardcoded computer or
GPU model name. Default decoding and attention behavior follow the pinned backend.

## Choose the work your computer should do

| Control | Effect |
|---|---|
| Base / Small / Medium | Explicit model choice; changes memory needs and recognition trade-offs |
| Eco | Conservative CPU thread use; Auto stays on CPU |
| Balanced | Moderate CPU resources; Auto attempts installed, available NVIDIA support |
| Performance | More bounded CPU resources; Auto can attempt NVIDIA support |
| CPU | Uses the CPU path, even if GPU support is installed |
| GPU | Requires the configured CUDA backend; failure asks before a CPU retry |
| Fast decoding | Optional fewer-candidate decoding, with a possible accuracy cost |

No profile silently replaces the model you selected. Standard decoding is the
default. Fast explicitly chooses one beam and one candidate. It can be useful for
a draft, but is not an accuracy-preserving speed promise.

CPU/RAM and available NVIDIA hardware are detected locally. A card name alone is
not treated as compatibility proof: the CLI must confirm actual CUDA backend
initialization and complete inference. Auto can retry on CPU with the same model;
an explicitly selected GPU does not silently switch devices.

Model size, CPU instruction support, memory pressure, GPU/driver compatibility,
audio complexity, code-switching, decoding retries, disk speed, sustained cooling
and other applications all affect processing time. A three-hour video is not
expected to finish instantly. There is no universal speed or accuracy percentage.

## Resume and estimates

Long recordings are decoded in bounded audio chunks rather than loaded wholesale
into application memory. A completed chunk is checkpointed with the source
fingerprint and inference settings. A cancelled/interrupted chunk is not marked
complete. Generate with matching settings resumes completed work.

Changing source content, model, track, language, profile, decoding, backend or
chunk policy invalidates the checkpoint. Starting another task can replace the
single current checkpoint. Finished mode outputs and edits use the normal session
cache; switching back to an already completed mode does not rerun inference.

An estimate appears only after real progress is measurable. It applies to the
current inference pass and remains uncertain. English translation normally needs
both an original-recognition pass and a local audio-to-English pass.

## Measure on your own device

Install models and the runtime beforehand; this script never downloads them:

```powershell
.\.venv\Scripts\python scripts/benchmark_inference.py PATH\sample.wav --model small
.\.venv\Scripts\python scripts/benchmark_inference.py PATH\sample.wav --model small --fast --devices GPU
```

Use a licensed representative sample. The same selected model is used for the
CPU/GPU comparison. The local JSON report records detected hardware, settings,
sample duration, elapsed time, real-time factor and cue counts. It does not include
transcript content or upload anything. Reports are ignored development artifacts,
not application defaults or a model accuracy leaderboard.

Short samples are sensitive to startup overhead; long recordings may behave
differently. Do not present a sample result as a guaranteed full-video time.
Changing models or enabling Fast introduces a separate recognition trade-off.

## Keep export quality separate from inference speed

Inference settings do not change the original recording. Captioned MP4 export
uses a separate high-quality H.264 encode at the source dimensions and frame
 timestamps. Burning captions is not lossless. Compatible selected audio is copied;
otherwise the documented AAC fallback is used. Export speed depends on the media
and encoder, independently of speech recognition.
