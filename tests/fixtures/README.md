# Test corpus

Generate English, Hindi and Hinglish WAVs with `scripts/make_speech_fixtures.py`
using the open-source eSpeak NG 1.52.0 executable. Reference texts live in that
script. The project authors dedicate those short original reference sentences
and their generated recordings to CC0-1.0. No private user recording is required
or committed. Files go under ignored `.test-data/corpus`.

Synthetic audio validates the real offline inference path but is not evidence
of recognition quality on natural voices. Follow `docs/VALIDATION.md` for native
speaker acceptance checks and recorded limitations.
