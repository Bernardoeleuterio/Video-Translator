"""Wrapper around faster-whisper."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from src.types import ProgressEvent, TranscriptSegment
from utils.hardware import HardwareInfo


ProgressCallback = Callable[[ProgressEvent], None]


class WhisperTranscriber:
    """Lazy-load and run the configured Whisper model."""

    def __init__(self, config: dict, hardware: HardwareInfo, progress: ProgressCallback) -> None:
        self.config = config
        self.hardware = hardware
        self.progress = progress
        self._model: object | None = None

    def load(self) -> None:
        """Load faster-whisper only when a job starts."""

        try:
            from faster_whisper import WhisperModel

            model_name = self.config["whisper"].get("model", "large-v3")
            self.progress(
                ProgressEvent(
                    stage="model",
                    percent=3,
                    message=f"Carregando Whisper {model_name} em {self.hardware.device.upper()}...",
                )
            )
            self._model = WhisperModel(
                model_name,
                device=self.hardware.device,
                compute_type=self.hardware.compute_type,
                cpu_threads=self.hardware.cpu_threads,
            )
            self.progress(
                ProgressEvent(stage="model", percent=12, message="Modelo carregado com sucesso.")
            )
        except Exception:
            logging.exception("Falha ao carregar modelo Whisper.")
            raise

    def transcribe_chunks(
        self,
        chunks: list[Path],
        chunk_minutes: int,
        cancel_event: threading.Event,
    ) -> list[TranscriptSegment]:
        """Transcribe all chunks as Turkish and offset timestamps back to the full video."""

        if self._model is None:
            self.load()

        try:
            all_segments: list[TranscriptSegment] = []
            chunk_offset = max(60, int(chunk_minutes) * 60)
            total = max(1, len(chunks))
            for index, chunk in enumerate(chunks):
                if cancel_event.is_set():
                    raise RuntimeError("Processamento cancelado pelo usuario.")

                progress_base = 12 + (index / total) * 43
                self.progress(
                    ProgressEvent(
                        stage="transcription",
                        percent=progress_base,
                        message=f"Transcrevendo parte {index + 1}/{total} em turco...",
                    )
                )
                segments, info = self._model.transcribe(  # type: ignore[union-attr]
                    str(chunk),
                    language=self.config["language"].get("source", "tr"),
                    task="transcribe",
                    beam_size=int(self.config["whisper"].get("beam_size", 5)),
                    vad_filter=bool(self.config["whisper"].get("vad_filter", True)),
                    word_timestamps=True,
                )
                logging.info(
                    "Idioma detectado pelo Whisper: %s (probabilidade %.3f)",
                    getattr(info, "language", "desconhecido"),
                    getattr(info, "language_probability", 0.0),
                )

                absolute_offset = index * chunk_offset
                for segment in segments:
                    if cancel_event.is_set():
                        raise RuntimeError("Processamento cancelado pelo usuario.")
                    text = str(getattr(segment, "text", "")).strip()
                    if text:
                        all_segments.append(
                            TranscriptSegment(
                                start=float(getattr(segment, "start", 0.0)) + absolute_offset,
                                end=float(getattr(segment, "end", 0.0)) + absolute_offset,
                                text=text,
                            )
                        )

            self.progress(
                ProgressEvent(
                    stage="transcription",
                    percent=55,
                    message=f"Transcricao concluida com {len(all_segments)} segmentos.",
                )
            )
            return all_segments
        except Exception:
            logging.exception("Falha durante transcricao.")
            raise
