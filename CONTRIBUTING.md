# Contributing to Subloom

Subloom aims to do one local subtitle workflow well. Keep changes small and
maintain the separation between UI, media tools, speech inference, transformations,
sessions and exports. Read AGENTS.md for the MVP scope and excluded future features.

1. Follow [development setup](docs/DEVELOPMENT.md).
2. Add or update meaningful tests for changed behavior.
3. Run Ruff and the applicable tests. Report which model, OS and hardware checks
   ran, skipped or remain unverified.
4. Explain the user-visible problem, resulting behavior and relevant validation.

Preserve original media and raw recognition results. Keep inference offline and
model/runtime downloads explicit, trusted and verified. Do not add telemetry,
automatic uploads, cloud AI dependencies or fabricated progress/benchmarks.

Do not commit recordings, model files, transcripts, session JSON, credentials,
virtual environments, generated installers or build output. Use licensed or
locally generated test fixtures. Remove private text/paths from issues, logs,
screenshots and bug reports before sharing them.

For UI changes, check dark popups, keyboard access, playback/seek/edit synchronization,
busy/cancel states and small logical window sizes. For inference or media changes,
verify timestamps, cancellation, caching and source-file preservation.

Contributions are provided under the project's GPL-3.0-or-later license. Check
third-party licenses before introducing code, fonts, models or binaries. Public
binary releases must include required notices and corresponding-source access.
