"""FFmpeg integration used to inspect and split media safely."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path


SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".avi"}


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
    """Return media duration in seconds using ffprobe."""

    try:
        command = [
            "ffprobe",
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
    except FileNotFoundError as exc:
        logging.exception("ffprobe nao encontrado.")
        raise RuntimeError("FFmpeg/ffprobe nao encontrado no PATH.") from exc
    except Exception:
        logging.exception("Falha ao obter duracao de %s", video_path)
        raise


def extract_audio_chunks(video_path: Path, chunk_minutes: int) -> list[Path]:
    """Extract audio into WAV chunks to keep Whisper memory usage predictable."""

    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="video_translator_"))
        chunk_seconds = max(60, int(chunk_minutes) * 60)
        output_pattern = temp_dir / "chunk_%03d.wav"
        command = [
            "ffmpeg",
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
    except FileNotFoundError as exc:
        logging.exception("ffmpeg nao encontrado.")
        raise RuntimeError("FFmpeg nao encontrado no PATH.") from exc
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
        subtitle = str(subtitle_path).replace("\\", "/").replace(":", r"\:")
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"subtitles='{subtitle}'",
            "-c:a",
            "copy",
            str(output_path),
        ]
        subprocess.run(command, capture_output=True, text=True, check=True)
        return output_path
    except Exception:
        logging.exception("Falha ao incorporar legenda ao video.")
        raise
