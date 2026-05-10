from pathlib import Path

from shortsmaker.captions import build_captions, split_caption_chunks, write_ass, write_srt
from shortsmaker.renderer import ffmpeg_subtitle_path
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
