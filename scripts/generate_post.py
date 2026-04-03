import argparse
import base64
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from openai import OpenAI
from youtube_transcript_api import NoTranscriptFound
from youtube_transcript_api import TranscriptsDisabled
from youtube_transcript_api import YouTubeTranscriptApi
from yt_dlp import YoutubeDL

try:
    from scripts.quality import validate_markdown
except ModuleNotFoundError:
    from quality import validate_markdown


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
POSTS_DIR = ROOT_DIR / "_posts"
DRAFTS_DIR = ROOT_DIR / "_drafts"
IMAGES_DIR = ROOT_DIR / "assets" / "images"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ADsP blog post from a YouTube URL.")
    parser.add_argument("--youtube-url", required=True, help="Target YouTube URL")
    parser.add_argument("--publish", default="false", choices=["true", "false"], help="Whether to publish into _posts")
    parser.add_argument("--whitelist-config", default=str(CONFIG_DIR / "whitelist.json"))
    parser.add_argument("--quality-config", default=str(CONFIG_DIR / "quality_rules.json"))
    return parser.parse_args()


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text.lower()[:80]


def sec_to_mmss(seconds: float) -> str:
    total = int(seconds)
    minutes = total // 60
    secs = total % 60
    return f"{minutes:02}:{secs:02}"


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        return parsed.path.lstrip("/")
    if "youtube.com" in parsed.netloc:
        query = parse_qs(parsed.query)
        if "v" in query:
            return query["v"][0]
    raise ValueError("Unsupported YouTube URL format.")


def get_playlist_id(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "list" in query:
        return query["list"][0]
    return None


def fetch_video_metadata(url: str) -> dict[str, Any]:
    # Avoid yt-dlp for metadata in CI: YouTube often blocks unauthenticated scraping ("confirm you're not a bot").
    # oEmbed is lightweight and usually accessible without cookies.
    oembed_url = f"https://www.youtube.com/oembed?format=json&url={quote(url, safe='')}"
    request = Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    title = data.get("title") or "ADsP 학습 영상"
    channel = data.get("author_name") or "Unknown Channel"
    return {
        "title": title,
        "channel": channel,
        "uploader": channel,
        "webpage_url": url,
        "playlist_title": None,
        "channel_id": None,
    }


def validate_whitelist(url: str, metadata: dict[str, Any], whitelist: dict[str, Any]) -> None:
    channel_id = metadata.get("channel_id")
    channel_name = (metadata.get("channel") or metadata.get("uploader") or "").strip()
    playlist_id = get_playlist_id(url)
    title = metadata.get("title", "")

    allowed_channel_ids: list[str] = whitelist.get("allowed_channel_ids", [])
    allowed_playlist_ids: list[str] = whitelist.get("allowed_playlist_ids", [])
    allowed_title_keywords: list[str] = whitelist.get("allowed_title_keywords", [])
    allowed_channel_name_keywords: list[str] = whitelist.get("allowed_channel_name_keywords", [])

    strict_channel = bool(whitelist.get("strict_channel_match", False))
    strict_playlist = bool(whitelist.get("strict_playlist_match", False))

    if allowed_channel_ids:
        if not channel_id:
            if strict_channel:
                raise ValueError("Channel ID missing; cannot validate channel whitelist.")
        elif channel_id not in allowed_channel_ids:
            raise ValueError(f"Channel is not allowed. channel_id={channel_id}")

    if allowed_playlist_ids:
        if not playlist_id:
            if strict_playlist:
                raise ValueError("Playlist ID missing from URL; include a URL with '?list=...'.")
        elif playlist_id not in allowed_playlist_ids:
            raise ValueError(f"Playlist is not allowed. playlist_id={playlist_id}")

    if allowed_channel_name_keywords:
        channel_lower = channel_name.lower()
        has_channel_keyword = any(keyword.lower() in channel_lower for keyword in allowed_channel_name_keywords)
        if not has_channel_keyword:
            raise ValueError(f"Channel name is not allowed. channel={channel_name}")

    if allowed_title_keywords:
        title_lower = title.lower()
        has_keyword = any(keyword.lower() in title_lower for keyword in allowed_title_keywords)
        if not has_keyword:
            raise ValueError("Video title does not match ADsP 1st-subject keyword whitelist.")


@dataclass
class TranscriptChunk:
    start: float
    text: str


def get_transcript_from_youtube(video_id: str) -> list[TranscriptChunk]:
    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
    chunks: list[TranscriptChunk] = []
    for entry in transcript:
        chunks.append(TranscriptChunk(start=float(entry.get("start", 0)), text=str(entry.get("text", "")).strip()))
    return chunks


def get_transcript_via_whisper(url: str, client: OpenAI) -> list[TranscriptChunk]:
    with tempfile.TemporaryDirectory() as temp_dir:
        outtmpl = str(Path(temp_dir) / "audio.%(ext)s")
        with YoutubeDL(
            {
                "quiet": True,
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            }
        ) as ydl:
            ydl.download([url])

        audio_file = next(Path(temp_dir).glob("audio.*"))
        with audio_file.open("rb") as fp:
            result = client.audio.transcriptions.create(
                model=os.getenv("WHISPER_MODEL", "whisper-1"),
                file=fp,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

    chunks: list[TranscriptChunk] = []
    for segment in result.segments:
        if isinstance(segment, dict):
            text = str(segment.get("text", "")).strip()
            start = float(segment.get("start", 0) or 0)
        else:
            text = str(getattr(segment, "text", "")).strip()
            start = float(getattr(segment, "start", 0) or 0)
        if text:
            chunks.append(TranscriptChunk(start=start, text=text))
    return chunks


def collect_transcript(url: str, client: OpenAI) -> list[TranscriptChunk]:
    video_id = extract_video_id(url)
    try:
        return get_transcript_from_youtube(video_id)
    except (NoTranscriptFound, TranscriptsDisabled, RuntimeError, ValueError):
        if os.getenv("DISABLE_WHISPER", "false").lower() == "true":
            raise
        return get_transcript_via_whisper(url, client)


def chunks_to_prompt_text(chunks: list[TranscriptChunk], max_chars: int = 22000) -> str:
    lines = []
    current = 0
    for chunk in chunks:
        line = f"[{sec_to_mmss(chunk.start)}] {chunk.text}"
        if current + len(line) > max_chars:
            break
        lines.append(line)
        current += len(line) + 1
    return "\n".join(lines)


def generate_markdown_summary(client: OpenAI, title: str, channel: str, source_url: str, transcript_text: str) -> str:
    model = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-5-mini")
    system_prompt = (
        "너는 ADsP 수험생을 위한 전문 블로그 에디터다. "
        "출력은 한국어 Markdown 본문만 작성하고, 반드시 학습노트형 구조를 따른다."
    )
    user_prompt = f"""
다음 유튜브 학습 영상의 내용을 바탕으로 블로그 본문을 작성해줘.

요구사항:
1) 제목은 H1으로 시작: "# {title} 학습노트"
2) 반드시 다음 섹션 포함:
   - "## 핵심 요약"
   - "## 개념 정리"
   - "## 예상 문제"
3) 각 일반 문단 끝에는 반드시 다음 형식의 출처를 붙여:
   [출처: {title}, MM:SS]
4) 하단에는 "## References" 섹션을 만들고, 아래 정보를 포함:
   - 채널명: {channel}
   - 영상 URL: {source_url}
5) 영상 내용을 그대로 길게 베끼지 말고, 학습용으로 재구성해 요약해.
6) 최소 1,200자 이상 작성.

영상 전사(타임스탬프 포함):
{transcript_text}
"""
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    markdown = (getattr(response, "output_text", "") or "").strip()
    if not markdown and hasattr(response, "output"):
        parts: list[str] = []
        for item in response.output:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") in {"output_text", "text"}:
                    value = getattr(content, "text", "")
                    if value:
                        parts.append(str(value))
        markdown = "\n".join(parts).strip()
    if not markdown:
        raise RuntimeError("Model returned empty markdown.")
    return markdown


def generate_image(client: OpenAI, title: str, slug: str) -> str:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    image_filename = f"{date_str}-{slug}.png"
    output_path = IMAGES_DIR / image_filename

    image_prompt = (
        f"Create a clean educational illustration for ADsP study notes titled '{title}'. "
        "Use flat vector-like style, Korean exam-study mood, charts/icons/books, "
        "blue/teal palette, no real people, no text in image."
    )
    image_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    result = client.images.generate(model=image_model, prompt=image_prompt, size="1536x1024")

    image_base64 = result.data[0].b64_json
    if not image_base64:
        raise RuntimeError("Image generation failed: empty payload.")
    output_path.write_bytes(base64.b64decode(image_base64))
    return f"/assets/images/{image_filename}"


def render_post_markdown(
    title: str,
    source_url: str,
    source_channel: str,
    source_playlist: str,
    image_path: str,
    body_markdown: str,
) -> str:
    date_str = datetime.now().isoformat(timespec="seconds")
    front_matter = f"""---
title: "{title}"
date: {date_str}
tags: ["ADsP", "데이터이해", "데이터에듀"]
source_url: "{source_url}"
source_channel: "{source_channel}"
source_playlist: "{source_playlist}"
generated_image: "{image_path}"
ai_generated: true
---
"""
    ai_notice = "\n> 이 글은 AI 보조로 생성되었으며, 원본 영상 학습 내용을 요약한 자료입니다.\n"
    hero = f"\n![대표 이미지]({image_path})\n"
    return front_matter + hero + ai_notice + "\n" + body_markdown.strip() + "\n"


def write_post_file(markdown: str, title: str, publish: bool) -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title)
    target_dir = POSTS_DIR if publish else DRAFTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{date_str}-{slug}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    publish = args.publish.lower() == "true"
    whitelist = load_json(Path(args.whitelist_config))
    quality_cfg = load_json(Path(args.quality_config))

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    metadata = fetch_video_metadata(args.youtube_url)
    validate_whitelist(args.youtube_url, metadata, whitelist)

    transcript_chunks = collect_transcript(args.youtube_url, client)
    if not transcript_chunks:
        raise RuntimeError("No transcript content available.")

    transcript_for_prompt = chunks_to_prompt_text(transcript_chunks)
    title = metadata.get("title", "ADsP 학습 영상")
    channel = metadata.get("channel", metadata.get("uploader", "Unknown Channel"))
    playlist = metadata.get("playlist_title", "ADsP 1과목 데이터 이해")
    source_url = metadata.get("webpage_url", args.youtube_url)

    body_markdown = generate_markdown_summary(client, title, channel, source_url, transcript_for_prompt)
    image_slug = slugify(title)
    image_path = generate_image(client, title, image_slug)

    report = validate_markdown(
        markdown_text=body_markdown,
        min_body_chars=int(quality_cfg.get("min_body_chars", 1000)),
        min_citation_count=int(quality_cfg.get("min_citation_count", 6)),
        banned_terms=list(quality_cfg.get("banned_terms", [])),
    )
    if not report.ok:
        raise RuntimeError("Quality gate failed:\n- " + "\n- ".join(report.failures))

    post_markdown = render_post_markdown(
        title=title,
        source_url=source_url,
        source_channel=channel,
        source_playlist=playlist,
        image_path=image_path,
        body_markdown=body_markdown,
    )
    target_path = write_post_file(post_markdown, title, publish=publish)
    print(f"Generated post: {target_path}")
    print(f"Generated image: {image_path}")


if __name__ == "__main__":
    main()
