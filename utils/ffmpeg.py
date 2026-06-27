"""FFmpeg integration used to inspect and split media safely."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".avi"}


def _resolve_ffmpeg() -> str:
    """Return a usable FFmpeg executable from PATH or imageio-ffmpeg."""

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        logging.exception("FFmpeg nao encontrado no PATH nem via imageio-ffmpeg.")
        raise RuntimeError(
            "FFmpeg nao encontrado. Instale o FFmpeg ou execute "
            "`pip install imageio-ffmpeg`."
        ) from exc


def _resolve_ffprobe() -> str | None:
    """Return ffprobe from PATH when available."""

    return shutil.which("ffprobe")


def ensure_supported_video(video_path: Path) -> None:
    """Validate supported input extension."""

    try:
        if video_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError("Formato nao suportado. Use .mp4, .mkv ou .avi.")
        if not video_path.exists():
            raise FileNotFoundError(f"Video nao encontrado: {video_path}")
    except Exception:
        logging.exception("Video invalido: %s", video_path)
        raise


def get_video_duration(video_path: Path) -> float:
    """Return media duration in seconds using ffprobe or FFmpeg fallback."""

    try:
        ffprobe = _resolve_ffprobe()
        if ffprobe:
            command = [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())

        ffmpeg = _resolve_ffmpeg()
        result = subprocess.run(
            [ffmpeg, "-i", str(video_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
        if not match:
            raise RuntimeError("Nao foi possivel ler a duracao do video com FFmpeg.")
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:
        logging.exception("Falha ao obter duracao de %s", video_path)
        raise


def extract_audio_chunks(video_path: Path, chunk_minutes: int) -> list[Path]:
    """Extract audio into WAV chunks to keep Whisper memory usage predictable."""

    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="video_translator_"))
        chunk_seconds = max(60, int(chunk_minutes) * 60)
        output_pattern = temp_dir / "chunk_%03d.wav"
        ffmpeg = _resolve_ffmpeg()
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-reset_timestamps",
            "1",
            str(output_pattern),
        ]
        subprocess.run(command, capture_output=True, text=True, check=True)
        chunks = sorted(temp_dir.glob("chunk_*.wav"))
        if not chunks:
            raise RuntimeError("Nenhum chunk de audio foi gerado pelo FFmpeg.")
        return chunks
    except subprocess.CalledProcessError as exc:
        logging.exception("FFmpeg falhou: %s", exc.stderr)
        raise RuntimeError(f"Falha ao extrair audio: {exc.stderr}") from exc
    except Exception:
        logging.exception("Falha ao extrair audio de %s", video_path)
        raise


def burn_subtitle(video_path: Path, subtitle_path: Path) -> Path:
    """Create a copy of the video with the generated subtitle burned in."""

    try:
        output_path = video_path.with_name(f"{video_path.stem}.pt-BR.legendado{video_path.suffix}")
        # To avoid path escaping issues in Windows, run ffmpeg inside subtitle_path.parent directory and use relative path
        subtitle_filename = subtitle_path.name
        ffmpeg = _resolve_ffmpeg()
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path.resolve()),
            "-vf",
            f"subtitles='{subtitle_filename}'",
            "-c:a",
            "copy",
            str(output_path.resolve()),
        ]
        # Run subprocess with cwd=subtitle_path.parent
        subprocess.run(command, capture_output=True, text=True, check=True, cwd=str(subtitle_path.parent))
        return output_path
    except subprocess.CalledProcessError as exc:
        logging.exception("FFmpeg falhou ao embutir legenda (hard): %s", exc.stderr)
        raise RuntimeError(f"Erro no FFmpeg: {exc.stderr}") from exc
    except Exception:
        logging.exception("Falha ao incorporar legenda ao video.")
        raise


def mux_subtitle(video_path: Path, subtitle_path: Path) -> Path:
    """Mux the subtitle file as a text stream track (soft subtitle) without re-encoding."""

    try:
        output_path = video_path.with_name(f"{video_path.stem}.pt-BR.softsub{video_path.suffix}")
        ffmpeg = _resolve_ffmpeg()
        
        # Select correct subtitle codec: MP4 uses mov_text, MKV/AVI uses srt (subrip)
        suffix = video_path.suffix.lower()
        codec = "mov_text" if suffix == ".mp4" else "srt"
            
        command = [
            ffmpeg,
            "-y",
            "-i", str(video_path.resolve()),
            "-i", str(subtitle_path.resolve()),
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", codec,
            "-metadata:s:s:0", "language=por",
            "-metadata:s:s:0", "title=Português (Brasil)",
            str(output_path.resolve()),
        ]
        
        subprocess.run(command, capture_output=True, text=True, check=True)
        return output_path
    except subprocess.CalledProcessError as exc:
        logging.exception("FFmpeg falhou ao embutir legenda (soft): %s", exc.stderr)
        raise RuntimeError(f"Erro no FFmpeg: {exc.stderr}") from exc
    except Exception:
        logging.exception("Falha ao incorporar legenda (soft) ao video.")
        raise
