import os
import csv
import io
from functools import lru_cache
from dataclasses import dataclass
import shutil
import subprocess
import psutil


@dataclass(frozen=True)
class Hardware:
    cpus: int
    ram_gb: float
    available_gb: float
    gpu_name: str = ""
    vram_mb: int = 0
    gpu_driver: str = ""


@lru_cache(maxsize=1)
def nvidia() -> tuple[str, int, str]:
    cli = shutil.which("nvidia-smi")
    if not cli:
        return "", 0, ""
    try:
        result = subprocess.run([cli, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=3,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode == 0:
            row = next(csv.reader(io.StringIO(result.stdout)))
            return row[0].strip(), int(row[1].strip()), row[2].strip()
    except (OSError, ValueError, StopIteration, subprocess.TimeoutExpired):
        pass
    return "", 0, ""


def detect() -> Hardware:
    memory = psutil.virtual_memory()
    name, vram, driver = nvidia()
    return Hardware(os.cpu_count() or 2, memory.total / 1024**3, memory.available / 1024**3, name, vram, driver)


def threads(profile: str, cpus: int | None = None) -> int:
    count = cpus or os.cpu_count() or 2
    return {"Eco": max(1, min(2, count // 4)),
            "Balanced": max(1, min(6, count // 2)),
            "Performance": max(1, min(16, count - 1))}[profile]


def compatibility(model: str, hardware: Hardware) -> tuple[str, str]:
    required = {"base": 1.5, "small": 3.0, "medium": 6.0}[model]
    if hardware.available_gb < required:
        return "Not enough memory", f"Allow about {required:g} GB free RAM; currently {hardware.available_gb:.1f} GB free."
    if model == "medium" or hardware.cpus <= 4:
        return "May be slow", "CPU inference can take longer than the recording."
    return "Recommended", "Enough available RAM for CPU inference; speed depends on your processor."
