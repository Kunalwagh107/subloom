# Public Subloom visuals

These are intentional public documentation assets, not user media.

- `subloom-logo.svg` / `.png`: the application's existing logo.
- `subloom-banner.svg` / `.png`: a code-native banner using the same mark and colors.
- `welcome.png`, `models.png`, `editor.png`: real Qt application captures.
- `subloom-demo.mp4`: silent, automated capture of actual import, CPU inference,
  reference-based caption corrections, playback, SRT export and burned-caption MP4 export.
- `subloom-demo.gif`: a lower-resolution animated preview of the same capture.

The sample video is an original generated diagram. Its speech uses the CC0 English
reference from `scripts/make_speech_fixtures.py`. No personal recordings or profiles
are used. Visible captions have been manually reviewed; raw local ASR remains separate.
Capture performance is not representative of a long recording or another device.

Reproduce after explicitly installing Base and generating the English fixture:

```powershell
.\.venv\Scripts\python scripts/capture_readme.py --model-dir .test-data/models --speech .test-data/corpus/english.wav
```

The capture uses an isolated temporary profile and does not download anything.
For readable video-frame captures on hybrid-GPU systems, the capture process uses
Qt's CPU video decoding and OpenGL rendering. Application defaults are unchanged.
Only the named public assets are allowed into source-release archives; arbitrary
recordings/screenshots in this folder are excluded. See the root LICENSE for
Subloom artwork and THIRD_PARTY.md for dependencies.
