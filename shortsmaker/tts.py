"""Text-to-speech provider helpers for the ShortsMaker MVP."""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

from .captions import estimate_duration_seconds, normalize_story


def _write_silence(path: Path, duration_seconds: float, sample_rate: int = 22_050) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frame_count)
    return path


def synthesize_to_wav(text: str, output_path: Path, voice: str = "auto") -> tuple[Path, str]:
    """Create narration audio.

    The MVP uses locally installed command-line TTS tools when available. If none are
    installed, it creates a silent WAV with the estimated narration length so the
    video-render path remains testable and usable with a separately uploaded voiceover.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_story(text)
    provider = voice.lower()

    if provider in {"auto", "espeak"} and shutil.which("espeak"):
        subprocess.run(["espeak", "-w", str(output_path), normalized], check=True)
        return output_path, "espeak"

    if provider in {"auto", "espeak-ng"} and shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-w", str(output_path), normalized], check=True)
        return output_path, "espeak-ng"

    if provider in {"auto", "say"} and shutil.which("say"):
        subprocess.run(["say", "-o", str(output_path), "--data-format=LEI16@22050", normalized], check=True)
        return output_path, "say"

    _write_silence(output_path, estimate_duration_seconds(normalized))
    return output_path, "silent-fallback"


def wav_duration_seconds(path: Path) -> float | None:
    """Return WAV duration, or None when the file is not a readable WAV."""

    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / float(rate)
    except (wave.Error, FileNotFoundError, ZeroDivisionError):
        return None
