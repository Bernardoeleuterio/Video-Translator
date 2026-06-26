"""End-to-end video subtitle generation pipeline."""

from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from models.whisper_model import WhisperTranscriber
from src.subtitles import build_preview, normalize_cue_timing, write_srt
from src.translator import TranslationService
from src.types import ProcessingResult, ProgressEvent
from utils.ffmpeg import ensure_supported_video, extract_audio_chunks, get_video_duration
from utils.hardware import detect_hardware


ProgressCallback = Callable[[ProgressEvent], None]


class SubtitlePipeline:
    """Coordinates FFmpeg, Whisper, translation and SRT export."""

    def __init__(
        self,
        config: dict,
        progress: ProgressCallback,
        cancel_event: threading.Event,
    ) -> None:
        self.config = config
        self.progress = progress
        self.cancel_event = cancel_event

    def process(self, video_path: Path) -> ProcessingResult:
        """Generate a `.pt-BR.srt` subtitle next to the selected video."""

        started = time.monotonic()
        chunks: list[Path] = []
        try:
            ensure_supported_video(video_path)
            output_path = video_path.with_name(f"{video_path.stem}.pt-BR.srt")

            self.progress(
                ProgressEvent(stage="model", percent=1, message="Detectando hardware disponivel...")
            )
            hardware = detect_hardware(self.config)
            logging.info("Hardware selecionado: %s / %s", hardware.device, hardware.compute_type)

            duration = get_video_duration(video_path)
            chunk_minutes = int(self.config["processing"].get("chunk_minutes", 25))
            self.progress(
                ProgressEvent(
                    stage="transcription",
                    percent=10,
                    message=f"Extraindo audio e dividindo video de {duration / 60:.1f} min...",
                )
            )
            chunks = extract_audio_chunks(video_path, chunk_minutes)

            transcriber = WhisperTranscriber(self.config, hardware, self.progress)
            transcriber.load()
            transcript = transcriber.transcribe_chunks(chunks, chunk_minutes, self.cancel_event)

            if self.cancel_event.is_set():
                raise RuntimeError("Processamento cancelado pelo usuario.")

            translator = TranslationService(self.config, self.progress)
            translated = translator.translate(transcript, self.cancel_event)

            self.progress(
                ProgressEvent(stage="subtitle", percent=82, message="Ajustando sincronizacao e leitura...")
            )
            cues = normalize_cue_timing(translated, self.config)

            self.progress(
                ProgressEvent(stage="export", percent=92, message=f"Exportando legenda: {output_path.name}")
            )
            write_srt(cues, output_path)
            preview = build_preview(cues)

            elapsed = time.monotonic() - started
            self.progress(
                ProgressEvent(
                    stage="done",
                    percent=100,
                    message=f"Legenda concluida em {elapsed / 60:.1f} min.",
                    eta_seconds=0,
                )
            )
            return ProcessingResult(video_path=video_path, subtitle_path=output_path, preview=preview)
        except Exception:
            logging.exception("Falha ao processar video %s", video_path)
            self.progress(
                ProgressEvent(
                    stage="error",
                    percent=0,
                    message="Erro durante o processamento. Veja logs/app.log.",
                )
            )
            raise
        finally:
            if chunks and not bool(self.config["processing"].get("keep_temp_audio", False)):
                temp_dir = chunks[0].parent
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    logging.exception("Falha ao remover arquivos temporarios em %s", temp_dir)
