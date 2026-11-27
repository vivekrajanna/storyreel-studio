"""Local-only (127.0.0.1) preview & Content Calendar server for StoryReel Studio."""

import json
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from storyreel.config import load_config


def is_safe_subpath(base_dir: Path, target: Path) -> bool:
    """Ensure target path resolves strictly inside base_dir (blocks traversal & .env reads)."""
    try:
        target.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def load_studio_data(project_root: Path, handle: str = "@YourChannel") -> Dict[str, Any]:
    studio_file = project_root / "studio_data.json"
    output_dir = project_root / "output"
    if studio_file.is_file():
        data = json.loads(studio_file.read_text(encoding="utf-8"))
    else:
        data = {"channel": handle, "items": []}

    # Auto-discover built stories not yet in studio_data.json
    known_slugs = {item.get("slug") for item in data.get("items", []) if item.get("slug")}
    for ep_json in sorted(output_dir.glob("*/episode.json")):
        try:
            ep = json.loads(ep_json.read_text(encoding="utf-8"))
        except ValueError:
            continue
        slug = ep.get("slug", "")
        if slug and slug not in known_slugs:
            meta = ep.get("meta") or {}
            data.setdefault("items", []).append(
                {
                    "id": slug,
                    "slug": slug,
                    "episode_number": meta.get("episode_number", slug),
                    "series": meta.get("series", "Main Series"),
                    "format": "Long-Form",
                    "title": meta.get("title") or meta.get("title_en") or slug,
                    "status": "ready_to_upload",
                    "target_date": "",
                    "published_date": "",
                    "views": 0,
                    "likes": 0,
                    "youtube_url": "",
                    "notes": "",
                }
            )
            known_slugs.add(slug)

    for item in data.get("items", []):
        slug = item.get("slug") or ""
        ep_dir = output_dir / slug if slug else None
        has_player = bool(ep_dir and (ep_dir / "player.html").is_file())
        has_audio = bool(ep_dir and (ep_dir / "audio").is_dir() and list((ep_dir / "audio").rglob("*.wav")))
        item["has_player"] = has_player
        item["has_audio"] = has_audio
        item["player_url"] = f"{slug}/player.html" if has_player else ""
        item["reel_url"] = f"{slug}/reel.html" if (ep_dir and (ep_dir / "reel.html").is_file()) else ""
        item["thumb_url"] = f"{slug}/thumbnail.html" if (ep_dir and (ep_dir / "thumbnail.html").is_file()) else ""
    return data


def save_studio_data(project_root: Path, data: Dict[str, Any]) -> None:
    clean_items = [
        {k: v for k, v in item.items() if k not in ("has_player", "has_audio", "player_url", "reel_url", "thumb_url")}
        for item in data.get("items", [])
    ]
    out_obj = {"channel": data.get("channel", "@YourChannel"), "items": clean_items}
    (project_root / "studio_data.json").write_text(
        json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class StudioHandler(SimpleHTTPRequestHandler):
    project_root: Path = Path.cwd()
    channel_handle: str = "@YourChannel"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/studio":
            self._send_json(HTTPStatus.OK, load_studio_data(self.project_root, self.channel_handle))
            return
        # Explicitly verify translated static path stays inside output/
        translated = Path(self.translate_path(self.path))
        if not is_safe_subpath(self.project_root / "output", translated):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "Access outside output/ is forbidden"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in ("/api/studio/item", "/api/studio/add"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Unknown endpoint: {path}"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Body must be a JSON object")
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        data = load_studio_data(self.project_root, self.channel_handle)
        items = data.get("items", [])

        if path == "/api/studio/add":
            items.append(
                {
                    "id": str(payload.get("id") or f"idea_{len(items) + 1}").strip(),
                    "slug": str(payload.get("slug", "")).strip(),
                    "episode_number": str(payload.get("episode_number", "NEW")).strip(),
                    "series": str(payload.get("series", "Main Series")).strip(),
                    "format": str(payload.get("format", "Long-Form")).strip(),
                    "title": str(payload.get("title", "")).strip(),
                    "status": str(payload.get("status", "planned")).strip(),
                    "target_date": str(payload.get("target_date", "")).strip(),
                    "published_date": str(payload.get("published_date", "")).strip(),
                    "views": int(payload.get("views") or 0),
                    "likes": int(payload.get("likes") or 0),
                    "youtube_url": str(payload.get("youtube_url", "")).strip(),
                    "notes": str(payload.get("notes", "")).strip(),
                }
            )
            data["items"] = items
            save_studio_data(self.project_root, data)
            self._send_json(HTTPStatus.OK, load_studio_data(self.project_root, self.channel_handle))
            return

        target = next((it for it in items if it.get("id") == str(payload.get("id", "")).strip()), None)
        if not target:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Item not found"})
            return
        for field in ("status", "target_date", "published_date", "views", "likes", "youtube_url", "notes"):
            if field in payload:
                target[field] = int(payload[field] or 0) if field in ("views", "likes") else str(payload[field] or "").strip()
        save_studio_data(self.project_root, data)
        self._send_json(HTTPStatus.OK, load_studio_data(self.project_root, self.channel_handle))


def run_server(project_root: Path, host: str = "127.0.0.1", port: int = 8096) -> None:
    cfg = load_config(project_root)
    output_dir = project_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    class ConfiguredHandler(StudioHandler):
        pass

    ConfiguredHandler.project_root = project_root
    ConfiguredHandler.channel_handle = cfg["handle"]

    handler = partial(ConfiguredHandler, directory=str(output_dir))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"StoryReel Studio ({cfg['handle']}) running at http://{host}:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
