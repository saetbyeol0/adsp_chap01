import argparse
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect YouTube metadata for whitelist setup.")
    parser.add_argument("--youtube-url", required=True, help="YouTube watch URL (recommended) or playlist URL")
    return parser.parse_args()


def get_playlist_id(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    value = query.get("list", [None])[0]
    return value


def fetch_metadata(url: str) -> dict[str, Any]:
    with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if isinstance(info, dict) and "entries" in info and info.get("entries"):
        # If the user provided a playlist URL, ytdlp returns a playlist dict.
        # Grab the first entry for channel/video-level fields.
        first = next((e for e in info["entries"] if e), None)
        if isinstance(first, dict):
            first["playlist_title"] = info.get("title") or first.get("playlist_title")
            return first
    if not isinstance(info, dict):
        raise RuntimeError("Unexpected yt-dlp metadata shape.")
    return info


def main() -> None:
    args = parse_args()
    info = fetch_metadata(args.youtube_url)

    out = {
        "input_url": args.youtube_url,
        "webpage_url": info.get("webpage_url") or args.youtube_url,
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "channel_id": info.get("channel_id"),
        "playlist_id": get_playlist_id(args.youtube_url),
        "playlist_title": info.get("playlist_title"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
