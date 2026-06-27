"""Translation service for Turkish to Brazilian Portuguese."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from src.types import ProgressEvent, TranscriptSegment
from utils.text import normalize_text


ProgressCallback = Callable[[ProgressEvent], None]


def translate_with_gemini(text: str, api_key: str) -> str:
    """Translate batch text using Google Gemini API directly via HTTP request."""
    import urllib.request
    import json
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = (
        "Você é um tradutor especialista de séries turcas para português do Brasil. "
        "Traduza o texto a seguir mantendo as falas naturais, coloquiais, respeitando o contexto, pontuação e nomes próprios. "
        "Não traduza ou altere os delimitadores '=== [X] ==='. "
        "Retorne APENAS o texto traduzido, sem nenhuma introdução, notas ou comentários.\n\n"
        f"Texto para traduzir:\n{text}"
    )
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        try:
            return str(res_data['candidates'][0]['content']['parts'][0]['text']).strip()
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Resposta invalida do Gemini: {res_data}") from e


class TranslationService:
    """Translate transcript segments while preserving timing and proper names."""

    def __init__(self, config: dict, progress: ProgressCallback) -> None:
        self.config = config
        self.progress = progress

    def translate(
        self, segments: list[TranscriptSegment], cancel_event: threading.Event
    ) -> list[TranscriptSegment]:
        """Translate each segment to natural pt-BR in batches to prevent Google block."""

        try:
            from deep_translator import GoogleTranslator

            if not segments:
                return []

            translator = GoogleTranslator(source="tr", target="pt")
            
            # Group segments into batches under 4000 characters
            batches: list[list[TranscriptSegment]] = []
            current_batch: list[TranscriptSegment] = []
            current_char_count = 0
            
            for segment in segments:
                seg_len = len(segment.text) + 15
                if current_char_count + seg_len > 4000:
                    batches.append(current_batch)
                    current_batch = [segment]
                    current_char_count = seg_len
                else:
                    current_batch.append(segment)
                    current_char_count += seg_len
            if current_batch:
                batches.append(current_batch)
                
            translated: list[TranscriptSegment] = []
            total_batches = len(batches)
            started = time.monotonic()
            
            gemini_key = self.config.get("translation", {}).get("gemini_api_key", "")

            for b_idx, batch in enumerate(batches, start=1):
                if cancel_event.is_set():
                    raise RuntimeError("Processamento cancelado pelo usuario.")
                
                texts = [s.text for s in batch]
                separator = "\n=== [X] ===\n"
                combined = separator.join(texts)
                
                translated_texts = []
                success = False
                
                # Try Gemini translation if key is set
                if gemini_key:
                    try:
                        translated_combined = translate_with_gemini(combined, gemini_key)
                        parts = translated_combined.split("=== [X] ===")
                        parts = [p.strip() for p in parts]
                        
                        if len(parts) != len(texts):
                            import re
                            parts = re.split(r'===\s*\[[xX]\]\s*===', translated_combined)
                            parts = [p.strip() for p in parts]
                            
                        if len(parts) == len(texts):
                            translated_texts = parts
                            success = True
                        else:
                            logging.warning("Gemini Mismatch no lote %d. Usando fallback...", b_idx)
                    except Exception as e:
                        logging.warning("Falha com Gemini no lote %d: %s. Tentando Google...", b_idx, e)
                
                # Use Google Translator
                if not success:
                    try:
                        translated_combined = translator.translate(combined)
                        parts = translated_combined.split("=== [X] ===")
                        parts = [p.strip() for p in parts]
                        
                        if len(parts) != len(texts):
                            import re
                            parts = re.split(r'===\s*\[[xX]\]\s*===', translated_combined)
                            parts = [p.strip() for p in parts]
                            
                        if len(parts) == len(texts):
                            translated_texts = parts
                            success = True
                        else:
                            logging.warning("Google Translate Mismatch no lote %d. Usando fallback...", b_idx)
                    except Exception as e:
                        logging.warning("Falha no lote %d com Google: %s", b_idx, e)
                
                # Linear fallback if batch fails
                if not success:
                    translated_texts = []
                    for t in texts:
                        try:
                            translated_texts.append(translator.translate(t))
                        except Exception:
                            translated_texts.append(t)
                
                for segment, trans_text in zip(batch, translated_texts):
                    translated.append(
                        TranscriptSegment(
                            start=segment.start,
                            end=segment.end,
                            text=normalize_text(trans_text),
                        )
                    )

                elapsed = max(0.1, time.monotonic() - started)
                rate = b_idx / elapsed
                remaining = (total_batches - b_idx) / rate if rate else None
                percent = 55 + (b_idx / total_batches) * 25
                self.progress(
                    ProgressEvent(
                        stage="translation",
                        percent=percent,
                        message=f"Traduzindo lote {b_idx}/{total_batches} para pt-BR...",
                        eta_seconds=remaining,
                    )
                )
            return translated
        except Exception:
            logging.exception("Falha durante traducao.")
            raise
