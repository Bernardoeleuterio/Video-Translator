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
from utils.youtube import extract_video_id, get_youtube_subtitles, download_youtube_video


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

    def process(self, video_path: Path | None, youtube_url: str | None = None) -> ProcessingResult:
        """Generate a `.pt-BR.srt` subtitle next to the selected video or from a YouTube URL."""

        started = time.monotonic()
        chunks: list[Path] = []
        try:
            # If no local video but YouTube URL is provided, download the video first
            if video_path is None and youtube_url:
                self.progress(
                    ProgressEvent(
                        stage="model",
                        percent=5,
                        message="Baixando vídeo do YouTube para processamento local...",
                    )
                )
                output_dir = Path(self.config.get("interface", {}).get("default_folder", ""))
                if not output_dir or not output_dir.exists():
                    from src.config import ROOT_DIR
                    output_dir = ROOT_DIR / "output"
                
                def dl_progress(p: float) -> None:
                    # Map download percent (0-100) to progress percent (5-30)
                    percent = 5 + (p / 100) * 25
                    self.progress(
                        ProgressEvent(
                            stage="model",
                            percent=percent,
                            message=f"Baixando vídeo do YouTube ({p:.1f}%)...",
                        )
                    )
                
                video_path = download_youtube_video(youtube_url, output_dir, progress_cb=dl_progress)

            if video_path is None:
                raise ValueError("Nenhum arquivo de vídeo local ou URL do YouTube foi fornecido.")

            ensure_supported_video(video_path)
            output_path = video_path.with_name(f"{video_path.stem}.pt-BR.srt")

            transcript = None
            used_youtube_subtitles = False
            
            # Try to get subtitles directly from YouTube to avoid heavy transcription
            if youtube_url:
                video_id = extract_video_id(youtube_url)
                if video_id:
                    self.progress(
                        ProgressEvent(
                            stage="model",
                            percent=32,
                            message="Buscando legendas direto do YouTube...",
                        )
                    )
                    try:
                        transcript = get_youtube_subtitles(video_id)
                        used_youtube_subtitles = True
                        logging.info("Legendas obtidas direto do YouTube com sucesso. Pulando Whisper.")
                    except Exception as exc:
                        logging.warning("Não foi possível obter legendas do YouTube: %s. Usando transcrição local.", exc)

            # Fallback to local transcription using Whisper
            if transcript is None:
                self.progress(
                    ProgressEvent(
                        stage="model",
                        percent=35,
                        message="Detectando hardware disponível...",
                    )
                )
                hardware = detect_hardware(self.config)
                logging.info("Hardware selecionado: %s / %s", hardware.device, hardware.compute_type)

                duration = get_video_duration(video_path)
                chunk_minutes = int(self.config["processing"].get("chunk_minutes", 25))
                self.progress(
                    ProgressEvent(
                        stage="transcription",
                        percent=40,
                        message=f"Extraindo áudio e dividindo vídeo de {duration / 60:.1f} min...",
                    )
                )
                chunks = extract_audio_chunks(video_path, chunk_minutes)

                transcriber = WhisperTranscriber(self.config, hardware, self.progress)
                transcriber.load()
                transcript = transcriber.transcribe_chunks(chunks, chunk_minutes, self.cancel_event)

            if self.cancel_event.is_set():
                raise RuntimeError("Processamento cancelado pelo usuário.")

            translator = TranslationService(self.config, self.progress)
            translated = translator.translate(transcript, self.cancel_event)

            self.progress(
                ProgressEvent(stage="subtitle", percent=82, message="Ajustando sincronização e leitura...")
            )
            cues = normalize_cue_timing(translated, self.config)

            self.progress(
                ProgressEvent(stage="export", percent=92, message=f"Exportando legenda: {output_path.name}")
            )
            write_srt(cues, output_path)
            preview = build_preview(cues)

            elapsed = time.monotonic() - started
            method_name = "Via YouTube" if used_youtube_subtitles else "Via Whisper"
            self.progress(
                ProgressEvent(
                    stage="done",
                    percent=100,
                    message=f"Legenda concluída em {elapsed / 60:.1f} min ({method_name}).",
                    eta_seconds=0,
                )
            )
            return ProcessingResult(video_path=video_path, subtitle_path=output_path, preview=preview)
        except Exception:
            logging.exception("Falha ao processar vídeo %s", video_path)
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
                    logging.exception("Falha ao remover arquivos temporários em %s", temp_dir)
