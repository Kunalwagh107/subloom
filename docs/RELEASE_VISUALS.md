# Visual section for the GitHub release

Push the README and `docs/assets` files first so these public image URLs resolve.
Paste the following Markdown above the release notes, or use its images individually:

```markdown
![Subloom — make every word readable](https://raw.githubusercontent.com/Kunalwagh107/subloom/main/docs/assets/subloom-banner.svg)

Private subtitles for English, Hindi and Hinglish. Local AI, a simple editor,
and exports you can use anywhere.

### See it in action

[![Subloom app walkthrough](https://raw.githubusercontent.com/Kunalwagh107/subloom/main/docs/assets/subloom-demo.gif)](https://github.com/Kunalwagh107/subloom/blob/main/docs/assets/subloom-demo.mp4)

Real application capture using a short synthetic English recording and local
Whisper Base on CPU. Captions are reviewed in the editor. Silent walkthrough;
this is a workflow demonstration, not a speed benchmark.

### Review and edit

![Subloom editor](https://raw.githubusercontent.com/Kunalwagh107/subloom/main/docs/assets/editor.png)

### Choose your model

![Subloom model manager](https://raw.githubusercontent.com/Kunalwagh107/subloom/main/docs/assets/models.png)
```

For a video player directly in the release description, drag `docs/assets/subloom-demo.mp4`
into the release-notes text box and let GitHub finish the attachment upload. Adding
it only to the release's downloadable assets gives readers a download rather than
an inline walkthrough. Check the release Preview before publishing.

The standalone transparent logo is `docs/assets/subloom-logo.png`; the scalable
original is `subloom-logo.svg`. These visuals do not contain user recordings or
saved user profiles. See [asset provenance](assets/README.md).
