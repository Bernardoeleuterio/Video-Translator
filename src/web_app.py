"""Local web interface powered by FastAPI."""

from __future__ import annotations

import logging
import queue
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import ROOT_DIR, add_recent_video, load_config
from src.pipeline import SubtitlePipeline
from src.types import ProcessingResult, ProgressEvent
from utils.ffmpeg import SUPPORTED_EXTENSIONS, burn_subtitle
from utils.logger import LOG_FILE, setup_logging


WEB_DIR = ROOT_DIR / "web"
STATIC_DIR = WEB_DIR / "static"
UPLOAD_DIR = ROOT_DIR / "output" / "uploads"

JobStatus = Literal["queued", "running", "done", "error", "cancelled"]


@dataclass(slots=True)
class WebJob:
    id: str
    video_path: Path
    original_name: str
    status: JobStatus = "queued"
    stage: str = "model"
    percent: float = 0.0
    message: str = "Na fila."
    eta_seconds: float | None = None
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    subtitle_path: Path | None = None
    burned_video_path: Path | None = None
    burn_status: JobStatus = "queued"
    burn_message: str = "Video legendado ainda nao gerado."
    preview: str = ""
    error: str = ""


class JobManager:
    """Simple single-worker queue for heavy subtitle jobs."""

    def __init__(self) -> None:
        self.config = load_config()
        self.jobs: dict[str, WebJob] = {}
        self.cancel_events: dict[str, threading.Event] = {}
        self.work_queue: queue.Queue[str] = queue.Queue()
        self.lock = threading.Lock()
        self.worker = threading.Thread(target=self._run_forever, name="web-job-worker", daemon=True)
        self.worker.start()

    def create_job(self, video_path: Path, original_name: str) -> WebJob:
        try:
            if video_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError("Formato nao suportado. Use .mp4, .mkv ou .avi.")

            job = WebJob(
                id=uuid.uuid4().hex,
                video_path=video_path,
                original_name=original_name,
                created_at=time.time(),
            )
            with self.lock:
                self.jobs[job.id] = job
                self.cancel_events[job.id] = threading.Event()
            self.work_queue.put(job.id)
            return job
        except Exception:
            logging.exception("Falha ao criar job web.")
            raise

    def cancel_job(self, job_id: str) -> WebJob:
        try:
            with self.lock:
                job = self._get_job_locked(job_id)
                event = self.cancel_events[job_id]
                event.set()
                if job.status == "queued":
                    job.status = "cancelled"
                    job.message = "Cancelado."
                    job.finished_at = time.time()
                return job
        except Exception:
            logging.exception("Falha ao cancelar job %s", job_id)
            raise

    def get_job(self, job_id: str) -> WebJob:
        with self.lock:
            return self._get_job_locked(job_id)

    def list_jobs(self) -> list[WebJob]:
        with self.lock:
            return sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)

    def start_burn(self, job_id: str) -> WebJob:
        """Start creating a watch-ready video with burned subtitles."""

        with self.lock:
            job = self._get_job_locked(job_id)
            if job.status != "done" or job.subtitle_path is None:
                raise HTTPException(status_code=409, detail="Gere a legenda antes do video.")
            if job.burn_status == "running":
                return job
            if job.burn_status == "done" and job.burned_video_path and job.burned_video_path.exists():
                return job
            job.burn_status = "running"
            job.burn_message = "Gerando video com legenda embutida..."

        worker = threading.Thread(
            target=self._burn_video,
            args=(job_id,),
            name=f"burn-worker-{job_id[:8]}",
            daemon=True,
        )
        worker.start()
        return self.get_job(job_id)

    def _get_job_locked(self, job_id: str) -> WebJob:
        try:
            return self.jobs[job_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job nao encontrado.") from exc

    def _run_forever(self) -> None:
        while True:
            job_id = self.work_queue.get()
            try:
                self._process(job_id)
            except Exception:
                logging.exception("Worker web falhou no job %s", job_id)
            finally:
                self.work_queue.task_done()

    def _process(self, job_id: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            if job.status == "cancelled":
                return
            job.status = "running"
            job.started_at = time.time()
            job.message = "Iniciando processamento."

        try:
            self.config = add_recent_video(self.config, job.video_path)
            cancel_event = self.cancel_events[job_id]
            pipeline = SubtitlePipeline(
                self.config,
                progress=lambda event: self._update_progress(job_id, event),
                cancel_event=cancel_event,
            )
            result = pipeline.process(job.video_path)
            self._complete(job_id, result)
        except Exception as exc:
            with self.lock:
                job = self.jobs[job_id]
                if self.cancel_events[job_id].is_set():
                    job.status = "cancelled"
                    job.message = "Processamento cancelado."
                else:
                    job.status = "error"
                    job.error = str(exc)
                    job.message = "Erro durante o processamento. Veja logs/app.log."
                job.finished_at = time.time()

    def _update_progress(self, job_id: str, event: ProgressEvent) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.stage = event.stage
            job.percent = event.percent
            job.message = event.message
            job.eta_seconds = event.eta_seconds

    def _complete(self, job_id: str, result: ProcessingResult) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.status = "done"
            job.stage = "done"
            job.percent = 100.0
            job.message = "Legenda pronta."
            job.eta_seconds = 0
            job.subtitle_path = result.subtitle_path
            job.preview = result.preview
            job.finished_at = time.time()

    def _burn_video(self, job_id: str) -> None:
        try:
            with self.lock:
                job = self.jobs[job_id]
                video_path = job.video_path
                subtitle_path = job.subtitle_path
                if subtitle_path is None:
                    raise RuntimeError("Legenda inexistente para incorporar ao video.")

            output = burn_subtitle(video_path, subtitle_path)

            with self.lock:
                job = self.jobs[job_id]
                job.burned_video_path = output
                job.burn_status = "done"
                job.burn_message = "Video legendado pronto para assistir."
        except Exception as exc:
            logging.exception("Falha ao gerar video legendado para job %s", job_id)
            with self.lock:
                job = self.jobs[job_id]
                job.burn_status = "error"
                job.burn_message = str(exc)


setup_logging()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
manager = JobManager()
app = FastAPI(title="Video Translator Web", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def serialize_job(job: WebJob) -> dict:
    data = asdict(job)
    data["video_path"] = str(job.video_path)
    data["subtitle_path"] = str(job.subtitle_path) if job.subtitle_path else None
    data["burned_video_path"] = str(job.burned_video_path) if job.burned_video_path else None
    return data


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/jobs/upload")
async def upload_video(file: UploadFile = File(...)) -> dict:
    try:
        original_name = Path(file.filename or "video").name
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Formato nao suportado.")

        target = UPLOAD_DIR / f"{uuid.uuid4().hex}_{original_name}"
        with target.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        job = manager.create_job(target, original_name)
        return serialize_job(job)
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Falha no upload.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/jobs/path")
def create_job_from_path(video_path: str = Form(...)) -> dict:
    try:
        path = Path(video_path).expanduser().resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail="Arquivo nao encontrado.")
        job = manager.create_job(path, path.name)
        return serialize_job(job)
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("Falha ao criar job por caminho local.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [serialize_job(job) for job in manager.list_jobs()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return serialize_job(manager.get_job(job_id))


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    return serialize_job(manager.cancel_job(job_id))


@app.post("/api/jobs/{job_id}/burn")
def create_burned_video(job_id: str) -> dict:
    return serialize_job(manager.start_burn(job_id))


@app.get("/api/jobs/{job_id}/subtitle")
def download_subtitle(job_id: str) -> FileResponse:
    job = manager.get_job(job_id)
    if job.status != "done" or job.subtitle_path is None:
        raise HTTPException(status_code=409, detail="Legenda ainda nao esta pronta.")
    return FileResponse(
        job.subtitle_path,
        media_type="application/x-subrip",
        filename=job.subtitle_path.name,
    )


@app.get("/api/jobs/{job_id}/video")
def download_burned_video(job_id: str) -> FileResponse:
    job = manager.get_job(job_id)
    if job.burn_status != "done" or job.burned_video_path is None:
        raise HTTPException(status_code=409, detail="Video legendado ainda nao esta pronto.")
    return FileResponse(
        job.burned_video_path,
        media_type="video/mp4",
        filename=job.burned_video_path.name,
    )


@app.get("/api/logs")
def download_logs() -> FileResponse:
    LOG_FILE.touch(exist_ok=True)
    return FileResponse(LOG_FILE, media_type="text/plain", filename="app.log")


def main() -> None:
    import uvicorn

    uvicorn.run("src.web_app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
