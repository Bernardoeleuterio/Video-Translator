"""Hardware detection helpers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass(slots=True)
class HardwareInfo:
    """Detected processing capabilities."""

    device: str
    compute_type: str
    cpu_threads: int
    cuda_available: bool
    gpu_name: str | None = None


def detect_hardware(config: dict) -> HardwareInfo:
    """Detect CUDA support and choose the best available device."""

    cpu_threads = int(config.get("hardware", {}).get("cpu_threads") or os.cpu_count() or 1)
    use_gpu = bool(config.get("hardware", {}).get("use_gpu", True))
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        if use_gpu and cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            return HardwareInfo(
                device="cuda",
                compute_type=config["whisper"].get("compute_type_gpu", "float16"),
                cpu_threads=cpu_threads,
                cuda_available=True,
                gpu_name=gpu_name,
            )
        return HardwareInfo(
            device="cpu",
            compute_type=config["whisper"].get("compute_type_cpu", "int8"),
            cpu_threads=cpu_threads,
            cuda_available=cuda_available,
        )
    except Exception:
        logging.exception("Falha ao detectar CUDA; usando CPU.")
        return HardwareInfo(
            device="cpu",
            compute_type=config["whisper"].get("compute_type_cpu", "int8"),
            cpu_threads=cpu_threads,
            cuda_available=False,
        )
