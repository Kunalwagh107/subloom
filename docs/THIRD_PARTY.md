# Third-party inventory and release requirements

Subloom source is GPL-3.0-or-later. This choice is compatible with the selected
GPLv3-enabled FFmpeg build. Inference is whisper.cpp only; no PyTorch, cloud AI,
libmpv, Electron or browser runtime is required.

| Component | Pinned version | License / source |
|---|---|---|
| Python | 3.12 recommended | PSF; https://www.python.org/downloads/release/python-31210/ |
| PySide6, Shiboken6, Qt | 6.8.3 | LGPL-3.0/GPL alternatives; https://doc.qt.io/qtforpython-6/licenses.html |
| psutil | 6.1.1 | BSD-3-Clause; https://github.com/giampaolo/psutil/tree/release-6.1.1 |
| whisper.cpp + ggml | 1.8.3 | MIT; https://github.com/ggml-org/whisper.cpp/tree/v1.8.3 |
| Whisper multilingual weights | pinned HF commit `5359861c739e955e79d9a303bcbc70fb988958b1` | MIT; https://huggingface.co/ggerganov/whisper.cpp |
| FFmpeg (Gyan Essentials) | 7.1.1 | GPL-3.0-or-later enabled distribution; https://github.com/GyanD/codexffmpeg/releases/tag/7.1.1 |
| FFmpeg dependencies | as built by Gyan 7.1.1 | libass ISC, x264 GPL-2.0-or-later, FreeType FTL/GPL, HarfBuzz MIT, FriBidi LGPL, others: see distributor source/build configuration |
| Qt bundled FFmpeg | 7.1 (wheel) | LGPL-2.1-or-later build, separate from the CLI build; see Qt third-party attributions |
| PyInstaller (build only) | 6.12.0 | GPL with bootloader exception; https://pyinstaller.org/en/v6.12.0/license.html |
| Inno Setup (build only) | 6.7.3 | The compiler license distinguishes non-commercial and commercial use; https://jrsoftware.org/ and the compiler's license apply. Commercial builders must obtain the appropriate license. |
| NVIDIA CUDA runtime (optional separate component) | 12.4, as shipped by whisper.cpp 1.8.3 | NVIDIA CUDA EULA, not GPL; copies in `licenses/NVIDIA-CUDA-EULA.*`. Driver is not bundled. |
| pytest / pytest-qt / pysubs2 / Ruff (tests only) | see pyproject.toml | MIT / MIT / MIT / MIT respectively |

Archive SHA-256 values are recorded from the downloaded pinned release bytes in
`scripts/bootstrap_runtime.py`. Model SHA-256 and sizes come from the official
Hugging Face LFS manifest, not inferred values. Runtime and weights remain
separate; no weights are included in the application package. `ffplay` is unused.

## Redistribution

Keep Qt libraries dynamically linked and replaceable in the portable application
folder. Include LGPL/GPL notices and license copies; permit reverse engineering
for library debugging/relinking as required by the applicable licenses. Keep the
application source, build scripts and exact corresponding third-party source
available alongside a distributed binary release, following each component's
license. The package is a local build artifact, not a declaration that a public
redistribution release has completed all source-delivery obligations.

For a public binary release, publish the exact FFmpeg 7.1.1 distributor
corresponding source and build configuration (including enabled libraries),
whisper.cpp/ggml v1.8.3 sources, Qt/PySide6 6.8.3 corresponding source and notices,
and Subloom source/build instructions through the same release channel. Merely
linking to a moving upstream branch is not an adequate substitute for fulfilling
source-delivery obligations. Do not add arbitrary DLLs/models without recording
their license and provenance. Code-signing certificates are not supplied.

Windows system fonts (Segoe UI, Nirmala UI, Consolas) are used from the OS and
are not redistributed. The app relies on Nirmala UI for Devanagari caption burn-in
on normal Windows installations. Headless Linux tests use distribution fonts
with Devanagari coverage. Confirm font availability on release target systems.

## Test speech only

Original reference sentences in `scripts/make_speech_fixtures.py` are CC0-1.0.
An independently installed eSpeak NG executable (GPL-3.0-or-later) can produce
synthetic fixtures locally. It is test tooling, not an application dependency.
No speech-synthesis models or generated recordings are shipped. Use appropriately
licensed fixtures for acceptance checks; natural voice quality remains a separate
manual review. Private experiment tooling/data is excluded from source releases.

## Docker test image

The Dockerfile uses the official Python image, Debian packages, PySide6 and a
verified source build of whisper.cpp at the pinned commit. Debian FFmpeg/fonts
carry their distribution licenses and may differ in version from Windows assets.
The image is contributor tooling, not a Windows installer or a bundled GPU runtime.
