import random
from pathlib import Path

import shortsmaker.renderer as renderer
from shortsmaker.captions import build_captions, split_caption_chunks, write_ass, write_srt
from shortsmaker.renderer import (
    build_render_command,
    choose_background_start,
    ffmpeg_subtitle_path,
    should_loop_background,
)
from shortsmaker.tts import synthesize_to_wav, wav_duration_seconds


def test_caption_generation_writes_srt_and_ass(tmp_path: Path) -> None:
    story = "This is the first sentence. This is the second sentence with extra words."
    captions = build_captions(story, duration_seconds=6.0)

    assert len(captions) == 2
    assert captions[0].start == 0
    assert captions[-1].end == 6.0

    srt = write_srt(captions, tmp_path / "captions.srt")
    ass = write_ass(captions, tmp_path / "captions.ass")

    assert "00:00:00,000 -->" in srt.read_text(encoding="utf-8")
    assert "PlayResX: 1920" in ass.read_text(encoding="utf-8")
    assert "PlayResY: 1080" in ass.read_text(encoding="utf-8")


def test_long_sentence_is_split_into_readable_chunks() -> None:
    story = " ".join(["word"] * 50)
    chunks = split_caption_chunks(story, max_chars=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 40 for chunk in chunks)


def test_silent_tts_fallback_creates_readable_wav(tmp_path: Path) -> None:
    wav_path, provider = synthesize_to_wav("A short story for testing.", tmp_path / "voice.wav", "silent")

    assert provider == "silent-fallback"
    assert wav_path.exists()
    assert wav_duration_seconds(wav_path) is not None


def test_subtitle_path_is_escaped_for_ffmpeg() -> None:
    escaped = ffmpeg_subtitle_path(Path("folder:name/caption's.ass"))

    assert r"\:" in escaped
    assert r"\'" in escaped


def test_random_background_start_stays_inside_available_clip() -> None:
    start = choose_background_start(120.0, 30.0, randomize=True, rng=random.Random(4))

    assert 0.0 <= start <= 90.0
    assert choose_background_start(20.0, 30.0, randomize=True) == 0.0
    assert choose_background_start(120.0, 30.0, randomize=False) == 0.0


def test_background_looping_only_when_video_is_shorter_or_unknown() -> None:
    assert should_loop_background(None, 30.0) is True
    assert should_loop_background(20.0, 30.0) is True
    assert should_loop_background(120.0, 30.0) is False


def test_render_command_cuts_to_audio_and_seeks_random_background(monkeypatch) -> None:
    monkeypatch.setattr(renderer, "require_ffmpeg", lambda: "ffmpeg")

    command = build_render_command(
        Path("background.mp4"),
        Path("narration.wav"),
        Path("captions.ass"),
        Path("out.mp4"),
        duration_seconds=12.3456,
        background_start_seconds=42.0,
        loop_background=False,
    )

    assert "-stream_loop" not in command
    assert command[command.index("-ss") + 1] == "42.000"
    assert command[command.index("-t") + 1] == "12.346"
    assert command[-1] == "out.mp4"


def test_render_command_loops_short_background(monkeypatch) -> None:
    monkeypatch.setattr(renderer, "require_ffmpeg", lambda: "ffmpeg")

    command = build_render_command(
        Path("background.mp4"),
        Path("narration.wav"),
        Path("captions.ass"),
        Path("out.mp4"),
        duration_seconds=45.0,
        loop_background=True,
    )

    assert command[command.index("-stream_loop") + 1] == "-1"
    assert command[command.index("-t") + 1] == "45.000"
