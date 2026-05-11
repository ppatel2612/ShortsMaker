# ShortsMaker

ShortsMaker is an MVP for turning pasted story text into a downloadable, narrated, captioned **16:9 MP4** using a background video you provide.

The first working version is intentionally small: it runs locally, renders one video at a time, and keeps all generated files under `outputs/`.

## What the MVP can do

- Accept story text from a local web form or CLI.
- Accept a user-provided background video.
- Generate readable timed captions from the story text.
- Create narration with an installed local TTS command when available (`espeak`, `espeak-ng`, or macOS `say`).
- Accept an uploaded/pre-recorded narration audio file if you want a better voice.
- Render a downloadable **1920x1080, 16:9 MP4** with FFmpeg.
- Save intermediate files, captions, and a render manifest for each output.

## Requirements

- Python 3.11 or newer.
- FFmpeg installed and available on `PATH` for video rendering.
- Optional local TTS executable: `espeak`, `espeak-ng`, or macOS `say`.

If no TTS executable is installed and no narration audio is uploaded, the app creates silent placeholder audio so the render pipeline can still be exercised.

## Run the local web app

```bash
python -m shortsmaker.cli serve --host 127.0.0.1 --port 8000
```

Then open <http://127.0.0.1:8000>, paste the story, upload a background video, optionally upload narration audio, and click **Render 16:9 video**. When rendering finishes, the page provides a download link for `shortsmaker-16x9.mp4`.

## Render from the CLI

```bash
python -m shortsmaker.cli render \
  --story story.txt \
  --background background.mp4 \
  --narration narration.wav \
  --output-dir outputs/example
```

If `--narration` is omitted, ShortsMaker tries local TTS and falls back to silent placeholder audio.

## Output files

Each render folder contains:

- `shortsmaker-16x9.mp4` - final downloadable video.
- `captions.srt` - editable plain caption file.
- `captions.ass` - styled captions burned into the video.
- `narration.wav` or uploaded narration audio.
- `manifest.json` - render settings and artifact paths.

## Implementation notes

The render pipeline is:

1. Normalize and chunk story text.
2. Create or accept narration audio.
3. Estimate caption timing from narration duration.
4. Write SRT and styled ASS captions.
5. Use FFmpeg to scale/crop the background video to 1920x1080, burn captions, mix narration, and export MP4.

See [docs/IMPLEMENTATION_FEASIBILITY.md](docs/IMPLEMENTATION_FEASIBILITY.md) for broader product ideas, future improvements, and risks.
