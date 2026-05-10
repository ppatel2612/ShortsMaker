"""Small standard-library web app for the ShortsMaker MVP."""

from __future__ import annotations

import cgi
import html
import shutil
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .captions import build_captions, estimate_duration_seconds, write_ass, write_srt
from .renderer import render_video, write_manifest
from .tts import synthesize_to_wav, wav_duration_seconds

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ShortsMaker MVP</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 920px; margin: 2rem auto; padding: 0 1rem; }
    label { display: block; font-weight: 700; margin-top: 1rem; }
    textarea { width: 100%; min-height: 220px; }
    input, select, button { font: inherit; margin-top: .35rem; }
    button { padding: .7rem 1rem; cursor: pointer; }
    .note { color: #555; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 1rem; background: #fafafa; }
  </style>
</head>
<body>
  <h1>ShortsMaker MVP</h1>
  <p class="note">Create a downloadable <strong>16:9 MP4</strong> from story text, a background video, captions, and narration audio.</p>
  <form class="card" method="post" action="/render" enctype="multipart/form-data">
    <label for="story">Story text</label>
    <textarea id="story" name="story" required placeholder="Paste your story here..."></textarea>

    <label for="background">Background video</label>
    <input id="background" name="background" type="file" accept="video/*" required>

    <label for="narration">Optional narration audio</label>
    <input id="narration" name="narration" type="file" accept="audio/*">
    <p class="note">If you do not upload narration, the app tries local TTS tools such as espeak. If none exist, it creates silent placeholder audio.</p>

    <label for="voice">Narrator provider</label>
    <select id="voice" name="voice">
      <option value="auto">Auto local TTS</option>
      <option value="espeak">espeak</option>
      <option value="espeak-ng">espeak-ng</option>
      <option value="say">macOS say</option>
      <option value="silent">Silent fallback</option>
    </select>

    <button type="submit">Render 16:9 video</button>
  </form>
</body>
</html>
"""


class ShortsMakerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the MVP app."""

    server_version = "ShortsMakerMVP/0.1"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(INDEX_HTML)
            return
        if parsed.path == "/download":
            self._download(parse_qs(parsed.query).get("id", [""])[0])
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if urlparse(self.path).path != "/render":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        try:
            self._render()
        except Exception as exc:  # broad handler keeps web MVP user-friendly
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, html.escape(str(exc)))

    def _render(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )
        story = form.getfirst("story", "").strip()
        if not story:
            self.send_error(HTTPStatus.BAD_REQUEST, "Story text is required")
            return

        project_id = uuid.uuid4().hex
        project_dir = OUTPUTS / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "story.txt").write_text(story, encoding="utf-8")

        background = form["background"] if "background" in form else None
        if background is None or not getattr(background, "filename", ""):
            self.send_error(HTTPStatus.BAD_REQUEST, "Background video is required")
            return
        background_path = project_dir / Path(background.filename).name
        with background_path.open("wb") as file_obj:
            shutil.copyfileobj(background.file, file_obj)

        narration_path = project_dir / "narration.wav"
        provider = "uploaded"
        narration = form["narration"] if "narration" in form else None
        if narration is not None and getattr(narration, "filename", ""):
            narration_path = project_dir / Path(narration.filename).name
            with narration_path.open("wb") as file_obj:
                shutil.copyfileobj(narration.file, file_obj)
        else:
            voice = form.getfirst("voice", "auto")
            provider_voice = "silent" if voice == "silent" else voice
            narration_path, provider = synthesize_to_wav(story, narration_path, provider_voice)

        duration = wav_duration_seconds(narration_path) or estimate_duration_seconds(story)
        captions = build_captions(story, duration)
        srt_path = write_srt(captions, project_dir / "captions.srt")
        ass_path = write_ass(captions, project_dir / "captions.ass")
        output_path = project_dir / "shortsmaker-16x9.mp4"
        result = render_video(background_path, narration_path, ass_path, output_path)
        write_manifest(
            project_dir / "manifest.json",
            {
                "project_id": project_id,
                "aspect_ratio": "16:9",
                "width": 1920,
                "height": 1080,
                "tts_provider": provider,
                "duration_seconds": duration,
                "background": str(background_path),
                "narration": str(narration_path),
                "captions_srt": str(srt_path),
                "captions_ass": str(ass_path),
                "render": result,
            },
        )

        self._send_html(
            f"""<!doctype html><html><body>
            <h1>Render complete</h1>
            <p>Your 16:9 video is ready.</p>
            <p><a href="/download?id={project_id}" download>Download MP4</a></p>
            <p>TTS provider: {html.escape(provider)}</p>
            <p><a href="/">Render another</a></p>
            </body></html>"""
        )

    def _download(self, project_id: str) -> None:
        if not project_id or any(char not in "0123456789abcdef" for char in project_id):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid project id")
            return
        path = OUTPUTS / project_id / "shortsmaker-16x9.mp4"
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Rendered video not found")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Disposition", 'attachment; filename="shortsmaker-16x9.mp4"')
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as file_obj:
            shutil.copyfileobj(file_obj, self.wfile)

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the local web app."""

    OUTPUTS.mkdir(exist_ok=True)
    server = ThreadingHTTPServer((host, port), ShortsMakerHandler)
    print(f"ShortsMaker MVP running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
