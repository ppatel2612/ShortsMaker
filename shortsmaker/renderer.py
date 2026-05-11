"""FFmpeg rendering helpers for 16:9 ShortsMaker videos."""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderResult:
    """Metadata for a completed render."""

    output_path: Path
    command: list[str]
    width: int
    height: int
    duration_seconds: float | None
    background_start_seconds: float
    loop_background: bool


def require_ffmpeg() -> str:
    """Return the ffmpeg executable path or raise a helpful error."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is required to render videos. Install ffmpeg and make sure it is on PATH."
        )
    return ffmpeg


def media_duration_seconds(path: Path) -> float | None:
    """Return media duration with ffprobe, or None when it cannot be detected."""

    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return None

    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return None

    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def choose_background_start(
    background_duration_seconds: float | None,
    audio_duration_seconds: float,
    randomize: bool = True,
    rng: random.Random | None = None,
) -> float:
    """Choose a start time for the background clip.

    When the background video is longer than the narration, this can randomly pick
    a clip of exactly the required audio length. If the background is shorter,
    starts at zero so the renderer can loop it.
    """

    if (
        not randomize
        or background_duration_seconds is None
        or background_duration_seconds <= audio_duration_seconds
    ):
        return 0.0

    generator = rng or random.SystemRandom()
    latest_start = background_duration_seconds - audio_duration_seconds
    return generator.uniform(0.0, latest_start)


def should_loop_background(
    background_duration_seconds: float | None,
    audio_duration_seconds: float,
) -> bool:
    """Return whether FFmpeg should loop the background to cover the audio."""

    return background_duration_seconds is None or background_duration_seconds < audio_duration_seconds


def format_seconds(seconds: float) -> str:
    """Format seconds for FFmpeg arguments and manifests."""

    return f"{max(0.0, seconds):.3f}"


def ffmpeg_subtitle_path(path: Path) -> str:
    """Escape a subtitle path for FFmpeg filter syntax."""

    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def build_render_command(
    background_path: Path,
    narration_path: Path,
    subtitles_path: Path,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    duration_seconds: float | None = None,
    background_start_seconds: float = 0.0,
    loop_background: bool = True,
) -> list[str]:
    """Build an FFmpeg command that renders a 16:9 downloadable MP4."""

    ffmpeg = require_ffmpeg()
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"subtitles='{ffmpeg_subtitle_path(subtitles_path)}'"
    )
    command = [ffmpeg, "-y"]
    if loop_background:
        command.extend(["-stream_loop", "-1"])
    if background_start_seconds > 0:
        command.extend(["-ss", format_seconds(background_start_seconds)])
    command.extend(
        [
            "-i",
            str(background_path),
            "-i",
            str(narration_path),
            "-vf",
            vf,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
        ]
    )
    if duration_seconds is not None:
        command.extend(["-t", format_seconds(duration_seconds)])
    command.extend(
        [
            "-shortest",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return command


def render_video(
    background_path: Path,
    narration_path: Path,
    subtitles_path: Path,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    duration_seconds: float | None = None,
    background_start_seconds: float = 0.0,
    loop_background: bool = True,
) -> RenderResult:
    """Render the final video using FFmpeg."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = build_render_command(
        background_path,
        narration_path,
        subtitles_path,
        output_path,
        width,
        height,
        duration_seconds,
        background_start_seconds,
        loop_background,
    )
    subprocess.run(command, check=True)
    return RenderResult(
        output_path=output_path,
        command=command,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        background_start_seconds=background_start_seconds,
        loop_background=loop_background,
    )


def write_manifest(path: Path, data: dict) -> Path:
    """Write a JSON render manifest."""

    serializable = {
        key: (asdict(value) if hasattr(value, "__dataclass_fields__") else value)
        for key, value in data.items()
    }
    path.write_text(json.dumps(serializable, indent=2, default=str), encoding="utf-8")
    return path
