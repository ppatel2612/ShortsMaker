# Reddit Story Shorts Implementation Feasibility

## Short answer

Yes. A tool that turns a story text input into a captioned, narrated, 16:9 short-form video is technically feasible with current open-source media tooling. The fastest reliable path is to build the pipeline around FFmpeg for rendering, a pluggable text-to-speech provider for narration, and a caption alignment stage that can start simple and improve over time.

## Target output

- 16:9 MP4 video, usually 1920x1080.
- User-provided background video, randomly clipped when longer than narration, looped when shorter, trimmed, cropped, and optionally blurred or dimmed.
- Narration audio generated from the story text.
- Burned-in captions styled for Shorts/TikTok readability.
- Optional variants using different narrator voices, caption themes, and background clips.
- Project metadata for repeatable renders.

## Recommended MVP scope

The MVP should avoid upload automation and focus on producing a ready-to-post MP4 locally.

1. **Input**: pasted title and story body.
2. **Presets**: narrator voice, background video, caption style, output length target.
3. **Text processing**: clean Reddit formatting, split into sentence/phrase chunks, and optionally create multiple parts for long stories.
4. **TTS generation**: synthesize WAV narration through a provider interface.
5. **Caption timing**: create sentence-level captions first; add word-level highlighting later.
6. **Video render**: crop/scale the background to 16:9, randomly seek into long background videos, trim output to narration duration, mix narration with optional background audio/music, burn captions, and export MP4.
7. **Artifacts**: save audio, caption files, render settings, and final video under an output folder.

## Reference architecture

```text
Story text
  -> Text cleaner / segmenter
  -> TTS provider
  -> Audio file
  -> Caption aligner
  -> SRT/ASS captions
  -> Renderer
  -> final MP4

Background video + render preset ------------------------------^
```

## Component choices

| Component | Practical choice | Why |
| --- | --- | --- |
| Rendering | FFmpeg | Mature, scriptable, supports scaling/cropping, audio mixing, subtitles, and drawtext-style overlays. |
| Captions | ASS subtitles for styled captions; SRT for interchange | ASS gives better styling control; SRT is easy to inspect and reuse. |
| TTS | Pluggable provider interface | Lets the app start with a local/open-source engine and add paid cloud voices later. |
| Local TTS option | Piper or Coqui TTS | Piper is lightweight and local; Coqui TTS provides many model options but has heavier Python/GPU dependency considerations. |
| Alignment | Start with chunk duration estimates; upgrade to forced alignment or Whisper-family word timestamps | Simple estimates are enough for MVP sentence captions; precise karaoke-style captions need alignment. |
| UI | CLI first, then a web/desktop wrapper | A CLI proves the render pipeline quickly and can later power a GUI. |

## Evidence from existing tools

- FFmpeg has native filters for video processing and text rendering, including the `drawtext` filter and support for loading text from a file, which makes it suitable for automated caption rendering pipelines: <https://ffmpeg.org/ffmpeg-filters.html>.
- Piper is a local neural TTS system; the original `rhasspy/piper` repository was archived on October 6, 2025 and points development to `OHF-Voice/piper1-gpl`, so it should be treated as viable but with an active-fork check during implementation: <https://github.com/rhasspy/piper>.
- Coqui TTS offers a Python API, CLI synthesis, multi-speaker/model features, and released models, but its dependency and model licensing details must be reviewed before choosing it as the default voice provider: <https://github.com/coqui-ai/TTS>.
- Aeneas can generate synchronization maps between text fragments and narration audio, which is directly relevant for caption alignment, but its AGPL license is a constraint for distribution: <https://github.com/readbeyond/aeneas>.

## Required features beyond the original list

### Core production requirements

- **Story validation**: maximum length, estimated duration, profanity/adult-content flags, and required manual review before publishing.
- **Content rights tracking**: record whether the story text is original, licensed, public-domain, or user-provided with permission.
- **Background asset library**: store each video with source, license, tags, duration, and safe-crop area notes.
- **Voice/provider configuration**: narrator ID, speed, pitch, model path/API key, sample rate, and usage limits.
- **Caption style presets**: font, size, colors, outline, max words per line, vertical position, and safe margins.
- **Render manifest**: JSON file that records all inputs, versions, and settings for reproducibility.
- **Failure recovery**: do not rerun expensive TTS if only captions or background styling changes.
- **Preview mode**: render the first 10-20 seconds quickly for quality checks.

### Quality requirements

- Sentence normalization so TTS reads abbreviations, usernames, numbers, and punctuation naturally.
- Silence trimming and loudness normalization for narration.
- Automatic splitting into multiple parts when estimated duration exceeds the target platform length.
- Caption timing guardrails so captions do not flash too quickly or cover important visual regions.
- Background clip selection that chooses a random valid start time when the source video is longer than the narration.
- Optional background music ducking under narration.

### Compliance and safety requirements

- Avoid scraping or reposting Reddit content without permission or a clear rights workflow.
- Keep a per-project record of content source and license/permission status.
- Include a manual approval step before export or upload.
- Add a configurable blocklist for personally identifying information and sensitive topics.
- Do not include voice cloning unless the speaker consent workflow is explicit.

## Implementation plan

### Phase 1: CLI proof of concept

- Create a command such as `shortsmaker render --story story.txt --background bg.mp4 --voice narrator_a`.
- Generate TTS audio from cleaned text.
- Produce sentence-level SRT/ASS captions.
- Render a 1920x1080 MP4 with FFmpeg, cutting the output to the audio duration and optionally selecting a random clip from long background footage.
- Save a render manifest and intermediate files.

### Phase 2: Quality improvements

- Add narrator presets and background video presets.
- Add caption style presets and preview rendering.
- Add audio loudness normalization and background audio ducking.
- Add duration estimation and automatic multi-part splitting.

### Phase 3: GUI and batch generation

- Add a local web UI or desktop shell around the CLI.
- Support project templates and render queues.
- Add variant generation: same story with multiple voices/backgrounds.
- Add a manual review checklist.

### Phase 4: Optional publishing integrations

- Add export folders per platform.
- Add metadata generation for title/description/hashtags.
- Consider upload API integrations only after content rights, account safety, and platform policy checks are in place.

## Feasibility verdict

Implementation is feasible. The recommended first milestone is a local CLI that renders one complete short from a story text file and a background video. After that works reliably, build voice/background selection, better caption alignment, preview rendering, and a user interface on top of the same pipeline.

## Main risks

- **TTS naturalness**: free local voices may sound less human than paid cloud voices; keep TTS pluggable.
- **Caption timing**: sentence-level timings are easy; word-level highlight timing needs alignment or transcription.
- **Licensing**: background videos, story text, fonts, TTS models, and alignment libraries can each impose separate restrictions.
- **Platform policy changes**: YouTube/TikTok rules and API access can change, so upload automation should be optional and isolated.
- **Compute requirements**: local neural TTS and Whisper-style transcription may be slow without a GPU.
