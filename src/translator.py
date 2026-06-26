"""Translation service for Turkish to Brazilian Portuguese."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from src.types import ProgressEvent, TranscriptSegment
from utils.text import normalize_text


ProgressCallback = Callable[[ProgressEvent], None]


class TranslationService:
    """Translate transcript segments while preserving timing and proper names."""

    def __init__(self, config: dict, progress: ProgressCallback) -> None:
        self.config = config
        self.progress = progress

    def translate(
        self, segments: list[TranscriptSegment], cancel_event: threading.Event
    ) -> list[TranscriptSegment]:
        """Translate each segment to natural pt-BR using deep-translator."""

        try:
            from deep_translator import GoogleTranslator

            if not segments:
                return []

            translator = GoogleTranslator(source="tr", target="pt")
            translated: list[TranscriptSegment] = []
            total = len(segments)
            started = time.monotonic()

            for index, segment in enumerate(segments, start=1):
                if cancel_event.is_set():
                    raise RuntimeError("Processamento cancelado pelo usuario.")
                try:
                    text = translator.translate(segment.text)
                except Exception:
                    logging.exception("Falha ao traduzir segmento; mantendo texto original.")
                    text = segment.text

                translated.append(
                    TranscriptSegment(
                        start=segment.start,
                        end=segment.end,
                        text=normalize_text(text),
                    )
                )

                if index == total or index % 5 == 0:
                    elapsed = max(0.1, time.monotonic() - started)
                    rate = index / elapsed
                    remaining = (total - index) / rate if rate else None
                    percent = 55 + (index / total) * 25
                    self.progress(
                        ProgressEvent(
                            stage="translation",
                            percent=percent,
                            message=f"Traduzindo {index}/{total} segmentos para pt-BR...",
                            eta_seconds=remaining,
                        )
                    )
            return translated
        except Exception:
            logging.exception("Falha durante traducao.")
            raise
