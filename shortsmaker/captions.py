"""Caption generation helpers for the ShortsMaker MVP."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Caption:
    """A timed caption block."""

    index: int
    start: float
    end: float
    text: str


def normalize_story(text: str) -> str:
    """Normalize story text for narration and captions."""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"^>\s?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"[`*_#]", "", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned)
    return cleaned.strip()


def split_caption_chunks(text: str, max_chars: int = 84) -> list[str]:
    """Split text into readable caption chunks."""

    normalized = normalize_story(text)
    if not normalized:
        return []

    chunks: list[str] = []
    for sentence in _SENTENCE_BOUNDARY.split(normalized):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue

        words = sentence.split()
        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            if current and len(candidate) > max_chars:
                chunks.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            chunks.append(" ".join(current))

    return chunks


def estimate_duration_seconds(text: str, words_per_minute: int = 155) -> float:
    """Estimate narration duration from word count."""

    word_count = len(normalize_story(text).split())
    if word_count == 0:
        return 1.0
    return max(1.5, (word_count / words_per_minute) * 60.0)


def build_captions(text: str, duration_seconds: float | None = None) -> list[Caption]:
    """Build sentence/phrase-level captions across the target duration."""

    chunks = split_caption_chunks(text)
    if not chunks:
        return []

    duration = duration_seconds or estimate_duration_seconds(text)
    weights = [max(1, len(chunk.split())) for chunk in chunks]
    total_weight = sum(weights)
    captions: list[Caption] = []
    cursor = 0.0

    for index, (chunk, weight) in enumerate(zip(chunks, weights), start=1):
        block_duration = max(1.2, duration * (weight / total_weight))
        end = min(duration, cursor + block_duration)
        if index == len(chunks):
            end = duration
        captions.append(Caption(index=index, start=cursor, end=max(end, cursor + 0.5), text=chunk))
        cursor = captions[-1].end

    return captions


def _srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _ass_timestamp(seconds: float) -> str:
    centiseconds = int(math.floor(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centiseconds:02}"


def write_srt(captions: list[Caption], path: Path) -> Path:
    """Write captions as an SRT file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for caption in captions:
        blocks.append(
            f"{caption.index}\n"
            f"{_srt_timestamp(caption.start)} --> {_srt_timestamp(caption.end)}\n"
            f"{caption.text}\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def write_ass(captions: list[Caption], path: Path) -> Path:
    """Write captions as styled ASS subtitles for 16:9 video."""

    path.parent.mkdir(parents=True, exist_ok=True)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,5,2,2,160,160,96,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for caption in captions:
        escaped = (
            caption.text.replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("\n", r"\N")
        )
        events.append(
            f"Dialogue: 0,{_ass_timestamp(caption.start)},{_ass_timestamp(caption.end)},"
            f"Default,,0,0,0,,{escaped}"
        )
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return path
