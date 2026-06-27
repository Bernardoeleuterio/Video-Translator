"""YouTube downloader and transcript retriever utilities."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from src.types import TranscriptSegment

# Regex to extract 11-character YouTube video ID
YOUTUBE_RE = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)([\w-]{11})'
)


def extract_video_id(url: str) -> str | None:
    """Extract 11-character YouTube video ID from URL."""
    match = YOUTUBE_RE.search(url)
    return match.group(1) if match else None


def get_youtube_subtitles(video_id: str) -> list[TranscriptSegment]:
    """Retrieve Turkish subtitles (manual or auto-generated) from a YouTube video ID."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        logging.info("Buscando legendas do YouTube para o video ID: %s", video_id)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to find Turkish transcript, manual or auto-generated
        try:
            transcript = transcript_list.find_transcript(["tr"])
        except Exception:
            logging.info("Legenda turca direta nao encontrada. Tentando listar todas as legendas...")
            # If "tr" is not explicitly in list, let's look if there is an auto-generated one in list
            # Usually find_transcript handles it, but just in case:
            for t in transcript_list:
                if t.language_code == "tr":
                    transcript = t
                    break
            else:
                raise RuntimeError("Nenhuma legenda em turco (manual ou automatica) disponivel para este video.")

        data = transcript.fetch()
        segments: list[TranscriptSegment] = []
        for entry in data:
            start = float(entry["start"])
            duration = float(entry["duration"])
            text = str(entry["text"]).strip()
            if text:
                segments.append(
                    TranscriptSegment(
                        start=start,
                        end=start + duration,
                        text=text,
                    )
                )

        logging.info("Sucesso: %d segmentos obtidos do YouTube.", len(segments))
        return segments
    except Exception as exc:
        logging.exception("Falha ao obter legendas do YouTube para o ID %s", video_id)
        raise RuntimeError(f"Nao foi possivel obter legendas do YouTube: {exc}") from exc


def download_youtube_video(
    url: str,
    output_dir: Path,
    progress_cb: Callable[[float], None] | None = None,
) -> Path:
    """Download a video from YouTube using yt-dlp and track progress."""
    try:
        import yt_dlp

        output_dir.mkdir(parents=True, exist_ok=True)
        logging.info("Iniciando download do YouTube para URL: %s", url)

        def ytdl_hook(d: dict) -> None:
            if d.get("status") == "downloading" and progress_cb:
                # Retrieve percentage download from yt-dlp
                percent_str = d.get("_percent_str", "0%").replace("%", "").strip()
                try:
                    percent = float(percent_str)
                    progress_cb(percent)
                except ValueError:
                    pass

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
            "progress_hooks": [ytdl_hook],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # When yt-dlp merges video and audio, output file might change extension to mp4
            # prepare_filename might return .mkv if not merged, but merge_output_format is set to mp4.
            # Let's ensure the path matches the final merged file if it exists.
            path = Path(filename)
            if not path.exists():
                # Try replacing extension with mp4
                mp4_path = path.with_suffix(".mp4")
                if mp4_path.exists():
                    path = mp4_path
            logging.info("Download concluido. Arquivo salvo em: %s", path)
            return path
    except Exception as exc:
        logging.exception("Falha ao baixar video do YouTube.")
        raise RuntimeError(f"Erro no download do YouTube: {exc}") from exc
