"""CustomTkinter desktop interface."""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

from src.config import add_recent_video, load_config, save_config
from src.pipeline import SubtitlePipeline
from src.types import ProcessingResult, ProgressEvent
from utils.ffmpeg import SUPPORTED_EXTENSIONS, burn_subtitle
from utils.logger import LOG_FILE, setup_logging

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # pragma: no cover - optional runtime dependency
    DND_FILES = ""
    TkinterDnD = None  # type: ignore[assignment]


class SubtitleGeneratorApp(ctk.CTk):
    """Main application window with queue-based background processing."""

    def __init__(self) -> None:
        setup_logging()
        self.config = load_config()
        ctk.set_appearance_mode(self.config["interface"].get("theme", "dark"))
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("Gerador de Legendas Turco para Português")
        self.geometry(
            f"{self.config['interface'].get('window_width', 1100)}x"
            f"{self.config['interface'].get('window_height', 720)}"
        )
        self.minsize(960, 640)

        self.video_queue: list[Path] = []
        self.result: ProcessingResult | None = None
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.progress_queue: queue.Queue[ProgressEvent | ProcessingResult | Exception] = queue.Queue()
        self.current_job_started = 0.0

        self._build_layout()
        self._load_recent_videos()
        self._enable_drag_and_drop()
        self.after(200, self._poll_worker_queue)

    def _build_layout(self) -> None:
        """Create the complete interface."""

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Gerador de legendas pt-BR para séries em turco",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.grid(row=0, column=0, padx=24, pady=(18, 4), sticky="w")

        self.hardware_label = ctk.CTkLabel(
            header,
            text="Whisper large-v3 | idioma original: turco | destino: pt-BR",
            text_color=("gray35", "gray70"),
        )
        self.hardware_label.grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=18)
        content.grid_columnconfigure(0, weight=2)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(content, corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        youtube_frame = ctk.CTkFrame(left, fg_color="transparent")
        youtube_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 0))
        youtube_frame.grid_columnconfigure(1, weight=1)

        youtube_label = ctk.CTkLabel(youtube_frame, text="URL do YouTube (opcional):")
        youtube_label.grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.youtube_entry = ctk.CTkEntry(
            youtube_frame,
            placeholder_text="Cole o link do episódio do YouTube aqui..."
        )
        self.youtube_entry.grid(row=0, column=1, sticky="ew")

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=16, pady=16)
        actions.grid_columnconfigure(0, weight=1)

        self.select_button = ctk.CTkButton(
            actions,
            text="Selecionar vídeos",
            command=self._select_videos,
            height=38,
        )
        self.select_button.grid(row=0, column=0, sticky="w")

        self.start_button = ctk.CTkButton(
            actions,
            text="Iniciar",
            command=self._start_processing,
            height=38,
        )
        self.start_button.grid(row=0, column=1, padx=8)

        self.cancel_button = ctk.CTkButton(
            actions,
            text="Cancelar",
            command=self._cancel_processing,
            state="disabled",
            fg_color="#8a2f2f",
            hover_color="#6f2525",
            height=38,
        )
        self.cancel_button.grid(row=0, column=2)

        self.queue_box = ctk.CTkTextbox(left, wrap="word")
        self.queue_box.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.queue_box.insert("1.0", "Arraste episódios aqui ou use o botão Selecionar vídeos.\n")
        self.queue_box.configure(state="disabled")

        progress_area = ctk.CTkFrame(left, fg_color="transparent")
        progress_area.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        progress_area.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(progress_area, text="Aguardando vídeo.")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.eta_label = ctk.CTkLabel(progress_area, text="Tempo restante: --")
        self.eta_label.grid(row=0, column=1, sticky="e")

        self.progress = ctk.CTkProgressBar(progress_area)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.progress.set(0)

        right = ctk.CTkFrame(content, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        settings_label = ctk.CTkLabel(
            right, text="Configurações", font=ctk.CTkFont(size=18, weight="bold")
        )
        settings_label.grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        self.gpu_switch = ctk.CTkSwitch(
            right,
            text="Usar GPU NVIDIA quando disponível",
            command=self._save_settings,
        )
        self.gpu_switch.grid(row=1, column=0, sticky="w", padx=16, pady=4)
        if self.config["hardware"].get("use_gpu", True):
            self.gpu_switch.select()

        self.preview = ctk.CTkTextbox(right, wrap="word")
        self.preview.grid(row=2, column=0, sticky="nsew", padx=16, pady=12)
        self.preview.insert("1.0", "Pré-visualização da legenda aparecerá aqui.")
        self.preview.configure(state="disabled")

        footer = ctk.CTkFrame(right, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        footer.grid_columnconfigure((0, 1), weight=1)

        self.open_button = ctk.CTkButton(
            footer,
            text="Abrir legenda",
            command=self._open_subtitle,
            state="disabled",
        )
        self.open_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.burn_button = ctk.CTkButton(
            footer,
            text="Incorporar ao vídeo",
            command=self._burn_current_subtitle,
            state="disabled",
        )
        self.burn_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.logs_button = ctk.CTkButton(footer, text="Abrir logs", command=self._open_logs)
        self.logs_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _enable_drag_and_drop(self) -> None:
        """Enable drag and drop when tkinterdnd2 is installed."""

        if TkinterDnD is None:
            return
        try:
            TkinterDnD._require(self)  # type: ignore[attr-defined]
            self.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
        except Exception:
            logging.exception("Nao foi possivel ativar arrastar e soltar.")

    def _on_drop(self, event: Any) -> None:
        """Handle files dropped into the window."""

        try:
            raw_paths = self.tk.splitlist(event.data)
            self._add_videos([Path(path) for path in raw_paths])
        except Exception:
            logging.exception("Falha ao receber arquivos arrastados.")
            messagebox.showerror("Erro", "Não foi possível adicionar os arquivos arrastados.")

    def _select_videos(self) -> None:
        """Open file picker for one or more video files."""

        try:
            default_folder = self.config["interface"].get("default_folder") or str(Path.home())
            filenames = filedialog.askopenfilenames(
                title="Selecione os episódios",
                initialdir=default_folder,
                filetypes=[("Vídeos", "*.mp4 *.mkv *.avi"), ("Todos os arquivos", "*.*")],
            )
            self._add_videos([Path(name) for name in filenames])
        except Exception:
            logging.exception("Falha ao selecionar videos.")
            messagebox.showerror("Erro", "Falha ao selecionar vídeos.")

    def _add_videos(self, paths: list[Path]) -> None:
        """Add supported videos to the queue."""

        try:
            added = False
            for path in paths:
                if path.suffix.lower() in SUPPORTED_EXTENSIONS and path not in self.video_queue:
                    self.video_queue.append(path)
                    added = True
            if added:
                self._refresh_queue_box()
                self.status_label.configure(text=f"{len(self.video_queue)} vídeo(s) na fila.")
        except Exception:
            logging.exception("Falha ao adicionar videos a fila.")
            raise

    def _load_recent_videos(self) -> None:
        """Show recent video history below the current queue."""

        try:
            recent = self.config["interface"].get("recent_videos", [])
            if recent:
                self._write_queue_text(
                    "Histórico recente:\n" + "\n".join(f"- {item}" for item in recent[:10])
                )
        except Exception:
            logging.exception("Falha ao carregar historico.")

    def _refresh_queue_box(self) -> None:
        """Refresh visible queue state."""

        lines = ["Fila de processamento:"]
        lines.extend(f"{index}. {path}" for index, path in enumerate(self.video_queue, start=1))
        self._write_queue_text("\n".join(lines))

    def _write_queue_text(self, text: str) -> None:
        self.queue_box.configure(state="normal")
        self.queue_box.delete("1.0", "end")
        self.queue_box.insert("1.0", text)
        self.queue_box.configure(state="disabled")

    def _start_processing(self) -> None:
        """Start queue processing in a background thread."""

        try:
            if self.worker and self.worker.is_alive():
                return
            youtube_url = self.youtube_entry.get().strip()
            if not self.video_queue and not youtube_url:
                messagebox.showinfo("Sem vídeos", "Selecione pelo menos um vídeo ou insira uma URL do YouTube.")
                return
            self.cancel_event.clear()
            self.result = None
            self.open_button.configure(state="disabled")
            self.burn_button.configure(state="disabled")
            self.start_button.configure(state="disabled")
            self.cancel_button.configure(state="normal")
            self.current_job_started = time.monotonic()
            self.worker = threading.Thread(target=self._process_queue, name="subtitle-worker", daemon=True)
            self.worker.start()
        except Exception:
            logging.exception("Falha ao iniciar processamento.")
            messagebox.showerror("Erro", "Falha ao iniciar processamento.")

    def _process_queue(self) -> None:
        """Process all queued videos or the YouTube URL sequentially."""

        try:
            youtube_url = self.youtube_entry.get().strip()
            # If there is a YouTube URL and no local videos, run once for the URL
            if youtube_url and not self.video_queue:
                pipeline = SubtitlePipeline(self.config, self.progress_queue.put, self.cancel_event)
                result = pipeline.process(None, youtube_url=youtube_url)
                self.progress_queue.put(result)
            else:
                is_first = True
                while self.video_queue and not self.cancel_event.is_set():
                    video = self.video_queue.pop(0)
                    self.config = add_recent_video(self.config, video)
                    pipeline = SubtitlePipeline(self.config, self.progress_queue.put, self.cancel_event)
                    # Pair the YouTube URL with the first video in the queue, or None for subsequent ones
                    url_to_use = youtube_url if is_first else None
                    is_first = False
                    result = pipeline.process(video, youtube_url=url_to_use)
                    self.progress_queue.put(result)
            if self.cancel_event.is_set():
                self.progress_queue.put(RuntimeError("Processamento cancelado."))
        except Exception as exc:
            logging.exception("Worker finalizado com erro.")
            self.progress_queue.put(exc)

    def _poll_worker_queue(self) -> None:
        """Read worker events without blocking the GUI event loop."""

        try:
            while True:
                item = self.progress_queue.get_nowait()
                if isinstance(item, ProgressEvent):
                    self._apply_progress(item)
                elif isinstance(item, ProcessingResult):
                    self._apply_result(item)
                elif isinstance(item, Exception):
                    self._apply_error(item)
        except queue.Empty:
            pass
        finally:
            self.after(200, self._poll_worker_queue)

    def _apply_progress(self, event: ProgressEvent) -> None:
        """Update progress bar, status and ETA."""

        self.progress.set(max(0.0, min(1.0, event.percent / 100)))
        self.status_label.configure(text=event.message)
        if event.eta_seconds is not None:
            self.eta_label.configure(text=f"Tempo restante: {self._format_seconds(event.eta_seconds)}")
        elif event.percent > 0:
            elapsed = time.monotonic() - self.current_job_started
            estimated_total = elapsed / max(0.01, event.percent / 100)
            self.eta_label.configure(
                text=f"Tempo restante: {self._format_seconds(max(0, estimated_total - elapsed))}"
            )

    def _apply_result(self, result: ProcessingResult) -> None:
        """Show the latest generated subtitle."""

        self.result = result
        self._refresh_queue_box()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", result.preview or "Legenda gerada sem prévia disponível.")
        self.preview.configure(state="disabled")
        self.open_button.configure(state="normal")
        self.burn_button.configure(state="normal")
        if not self.video_queue:
            self.start_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")

    def _apply_error(self, error: Exception) -> None:
        """Display errors and restore controls."""

        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.status_label.configure(text=str(error))
        self.eta_label.configure(text="Tempo restante: --")
        if "cancelado" not in str(error).lower():
            messagebox.showerror("Erro", f"{error}\n\nConsulte {LOG_FILE}.")

    def _cancel_processing(self) -> None:
        """Signal the background worker to stop as soon as possible."""

        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_label.configure(text="Cancelando processamento...")

    def _save_settings(self) -> None:
        """Persist interface settings immediately."""

        try:
            self.config["hardware"]["use_gpu"] = bool(self.gpu_switch.get())
            self.config["interface"]["theme"] = "dark"
            save_config(self.config)
        except Exception:
            logging.exception("Falha ao salvar configuracoes da interface.")

    def _open_subtitle(self) -> None:
        """Open the generated subtitle with the default Windows application."""

        try:
            if self.result is None:
                return
            os.startfile(self.result.subtitle_path)  # type: ignore[attr-defined]
        except Exception:
            logging.exception("Falha ao abrir legenda.")
            messagebox.showerror("Erro", "Não foi possível abrir a legenda.")

    def _open_logs(self) -> None:
        """Open the application log file."""

        try:
            LOG_FILE.touch(exist_ok=True)
            os.startfile(LOG_FILE)  # type: ignore[attr-defined]
        except Exception:
            logging.exception("Falha ao abrir logs.")
            messagebox.showerror("Erro", "Não foi possível abrir os logs.")

    def _burn_current_subtitle(self) -> None:
        """Embed subtitles into the video (Choice of fast Soft-sub or slow Hard-burn)."""

        try:
            if self.result is None:
                return

            choice = messagebox.askyesnocancel(
                "Escolha o método de incorporação",
                "Como deseja incorporar a legenda ao vídeo?\n\n"
                "Sim: Rápido (Soft-Sub) - Adiciona a legenda como faixa selecionável em 2 segundos.\n"
                "Não: Lento (Hard-Burn) - Desenha a legenda diretamente na imagem (pode levar minutos).\n"
                "Cancelar: Desistir."
            )

            if choice is None:
                return

            if choice:
                self.status_label.configure(text="Mesclando legenda rápido...")
                from utils.ffmpeg import mux_subtitle
                output = mux_subtitle(self.result.video_path, self.result.subtitle_path)
                messagebox.showinfo("Concluído", f"Vídeo com legenda embutida criado (Mux):\n{output.name}")
            else:
                self.status_label.configure(text="Queimando legenda no vídeo (lento)...")
                
                def run_burn():
                    try:
                        output = burn_subtitle(self.result.video_path, self.result.subtitle_path)
                        self.after(0, lambda: messagebox.showinfo("Concluído", f"Vídeo legendado criado (Hard-burn):\n{output.name}"))
                    except Exception as e:
                        self.after(0, lambda: messagebox.showerror("Erro", f"Falha ao queimar legenda:\n{e}"))
                    finally:
                        self.after(0, lambda: self.status_label.configure(text="Processamento concluído."))

                threading.Thread(target=run_burn, daemon=True).start()

        except Exception as exc:
            messagebox.showerror("Erro", f"Falha ao incorporar legenda:\n{exc}")

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        seconds = max(0, int(seconds))
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes:02}min"
        if minutes:
            return f"{minutes}min {secs:02}s"
        return f"{secs}s"


def main() -> None:
    """Run the desktop application."""

    app = SubtitleGeneratorApp()
    app.mainloop()
