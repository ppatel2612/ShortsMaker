"""Command-line entry point for the ShortsMaker MVP."""

from __future__ import annotations

import argparse
from pathlib import Path

from .app import run
from .captions import build_captions, estimate_duration_seconds, write_ass, write_srt
from .renderer import (
    choose_background_start,
    media_duration_seconds,
    render_video,
    should_loop_background,
    write_manifest,
)
from .tts import synthesize_to_wav, wav_duration_seconds


def render_command(args: argparse.Namespace) -> None:
    story = Path(args.story).read_text(encoding="utf-8")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    narration = Path(args.narration) if args.narration else output_dir / "narration.wav"
    provider = "uploaded"
    if not args.narration:
        narration, provider = synthesize_to_wav(story, narration, args.voice)

    duration = (
        wav_duration_seconds(narration)
        or media_duration_seconds(narration)
        or estimate_duration_seconds(story)
    )
    background_path = Path(args.background)
    background_duration = media_duration_seconds(background_path)
    random_background = args.background_clip == "random"
    background_start = (
        args.background_start_seconds
        if args.background_start_seconds is not None
        else choose_background_start(background_duration, duration, random_background)
    )
    loop_background = should_loop_background(background_duration, duration)
    captions = build_captions(story, duration)
    srt_path = write_srt(captions, output_dir / "captions.srt")
    ass_path = write_ass(captions, output_dir / "captions.ass")
    output_path = output_dir / args.output_name
    result = render_video(
        background_path,
        narration,
        ass_path,
        output_path,
        duration_seconds=duration,
        background_start_seconds=background_start,
        loop_background=loop_background,
    )
    write_manifest(
        output_dir / "manifest.json",
        {
            "aspect_ratio": "16:9",
            "width": 1920,
            "height": 1080,
            "tts_provider": provider,
            "story": str(args.story),
            "duration_seconds": duration,
            "background_duration_seconds": background_duration,
            "background_start_seconds": background_start,
            "background_randomized": random_background and args.background_start_seconds is None,
            "background_looped": loop_background,
            "background": str(args.background),
            "narration": str(narration),
            "captions_srt": str(srt_path),
            "captions_ass": str(ass_path),
            "render": result,
        },
    )
    print(f"Rendered {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a 16:9 narrated story video.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the local web UI")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    render = subparsers.add_parser("render", help="Render a 16:9 MP4 from local files")
    render.add_argument("--story", required=True, help="Path to a text file containing the story")
    render.add_argument("--background", required=True, help="Path to the background video")
    render.add_argument("--narration", help="Optional narration audio file")
    render.add_argument("--voice", default="auto", help="TTS provider: auto, espeak, espeak-ng, say, or silent")
    render.add_argument(
        "--background-clip",
        choices=["random", "start"],
        default="random",
        help="Use a random clip from a long background video or start at 0 seconds",
    )
    render.add_argument(
        "--background-start-seconds",
        type=float,
        help="Optional exact background start time; overrides --background-clip",
    )
    render.add_argument("--output-dir", default="outputs/cli-render")
    render.add_argument("--output-name", default="shortsmaker-16x9.mp4")

    args = parser.parse_args()
    if args.command == "serve":
        run(args.host, args.port)
    elif args.command == "render":
        render_command(args)


if __name__ == "__main__":
    main()
