const uploadForm = document.querySelector("#uploadForm");
const videoFile = document.querySelector("#videoFile");
const pathForm = document.querySelector("#pathForm");
const videoPath = document.querySelector("#videoPath");
const jobList = document.querySelector("#jobList");
const statusPill = document.querySelector("#statusPill");
const stageValue = document.querySelector("#stageValue");
const etaValue = document.querySelector("#etaValue");
const progressBar = document.querySelector("#progressBar");
const progressValue = document.querySelector("#progressValue");
const messageValue = document.querySelector("#messageValue");
const cancelButton = document.querySelector("#cancelButton");
const downloadButton = document.querySelector("#downloadButton");
const previewValue = document.querySelector("#previewValue");

let activeJobId = null;
let jobs = [];

function formatEta(seconds) {
  if (seconds === null || seconds === undefined) return "--";
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${String(minutes % 60).padStart(2, "0")}min`;
  }
  if (minutes > 0) return `${minutes}min ${String(rest).padStart(2, "0")}s`;
  return `${rest}s`;
}

function setActiveJob(job) {
  activeJobId = job?.id ?? null;
  renderDetails(job);
  renderJobs();
}

function renderJobs() {
  jobList.innerHTML = "";
  if (jobs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "job-card";
    empty.innerHTML = "<strong>Nenhum episódio na fila</strong><span>-</span>";
    jobList.appendChild(empty);
    return;
  }

  for (const job of jobs) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `job-card ${job.id === activeJobId ? "active" : ""}`;
    card.innerHTML = `
      <div>
        <strong>${job.original_name}</strong>
        <span>${job.message}</span>
      </div>
      <span>${Math.round(job.percent)}%</span>
    `;
    card.addEventListener("click", () => setActiveJob(job));
    jobList.appendChild(card);
  }
}

function renderDetails(job) {
  const current = job ?? jobs.find((item) => item.id === activeJobId) ?? jobs[0];
  if (!current) {
    statusPill.textContent = "Aguardando";
    statusPill.className = "status-pill idle";
    stageValue.textContent = "-";
    etaValue.textContent = "--";
    progressBar.style.width = "0%";
    progressValue.textContent = "0%";
    messageValue.textContent = "Nenhum vídeo em execução.";
    cancelButton.disabled = true;
    downloadButton.classList.add("disabled");
    previewValue.textContent = "A legenda aparecerá aqui quando estiver pronta.";
    return;
  }

  activeJobId = current.id;
  const percent = Math.max(0, Math.min(100, current.percent));
  statusPill.textContent = current.status;
  statusPill.className = `status-pill ${current.status}`;
  stageValue.textContent = current.stage;
  etaValue.textContent = formatEta(current.eta_seconds);
  progressBar.style.width = `${percent}%`;
  progressValue.textContent = `${Math.round(percent)}%`;
  messageValue.textContent = current.error || current.message;
  cancelButton.disabled = !["queued", "running"].includes(current.status);
  cancelButton.dataset.jobId = current.id;

  if (current.status === "done") {
    downloadButton.href = `/api/jobs/${current.id}/subtitle`;
    downloadButton.classList.remove("disabled");
    previewValue.textContent = current.preview || "Legenda pronta.";
  } else {
    downloadButton.href = "#";
    downloadButton.classList.add("disabled");
    previewValue.textContent = current.preview || "Aguardando conclusão.";
  }
}

async function refreshJobs() {
  const response = await fetch("/api/jobs");
  jobs = await response.json();
  const active = jobs.find((job) => job.id === activeJobId) ?? jobs[0] ?? null;
  renderJobs();
  renderDetails(active);
}

async function createUploadJob(file) {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/jobs/upload", { method: "POST", body });
  if (!response.ok) throw new Error(await response.text());
  const job = await response.json();
  activeJobId = job.id;
  await refreshJobs();
}

async function createPathJob(path) {
  const body = new FormData();
  body.append("video_path", path);
  const response = await fetch("/api/jobs/path", { method: "POST", body });
  if (!response.ok) throw new Error(await response.text());
  const job = await response.json();
  activeJobId = job.id;
  await refreshJobs();
}

uploadForm.addEventListener("click", () => videoFile.click());
uploadForm.addEventListener("dragover", (event) => {
  event.preventDefault();
  uploadForm.classList.add("dragging");
});
uploadForm.addEventListener("dragleave", () => uploadForm.classList.remove("dragging"));
uploadForm.addEventListener("drop", async (event) => {
  event.preventDefault();
  uploadForm.classList.remove("dragging");
  const file = event.dataTransfer.files[0];
  if (file) await createUploadJob(file);
});
videoFile.addEventListener("change", async () => {
  const file = videoFile.files[0];
  if (file) await createUploadJob(file);
  videoFile.value = "";
});
pathForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = videoPath.value.trim();
  if (!value) return;
  await createPathJob(value);
  videoPath.value = "";
});
cancelButton.addEventListener("click", async () => {
  const jobId = cancelButton.dataset.jobId;
  if (!jobId) return;
  await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
  await refreshJobs();
});

setInterval(refreshJobs, 1500);
refreshJobs();
