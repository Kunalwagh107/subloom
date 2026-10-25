"""Bounded subprocess output, no shell, real cooperative cancellation."""
import os
import queue
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from .errors import Cancelled, SubloomError

Progress = Callable[[str, float | None], None]


class Cancellation:
    def __init__(self) -> None:
        self.event = threading.Event()

    def cancel(self) -> None:
        self.event.set()

    def check(self) -> None:
        if self.event.is_set():
            raise Cancelled("Cancelled. Your original media and saved captions are safe.")


def run(args: list[str], cancel: Cancellation, *, cwd: Path | None = None,
        line: Callable[[str], None] | None = None, timeout: float | None = None) -> str:
    cancel.check()
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        environment = os.environ.copy()
        environment.setdefault("PYTHONIOENCODING", "utf-8")
        proc = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=flags, env=environment)
    except OSError as exc:
        raise SubloomError(f"Cannot start {Path(args[0]).name}. Check installation and permissions: {exc}") from exc
    messages: queue.Queue[bytes | None] = queue.Queue(maxsize=256)

    def read() -> None:
        try:
            for item in iter(proc.stdout.readline, b""):
                messages.put(item)
        finally:
            messages.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    output: deque[str] = deque(maxlen=512)
    started = time.monotonic()
    done = False
    try:
        while not done:
            cancel.check()
            if timeout and time.monotonic() - started > timeout:
                raise SubloomError(f"{Path(args[0]).name} timed out. Check the dependency and input file.")
            try:
                item = messages.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                done = True
            else:
                decoded = item.decode("utf-8", errors="replace").strip()
                output.append(decoded)
                if line:
                    line(decoded)
        proc.wait(timeout=10)
        cancel.check()
        result = "\n".join(output)
        if proc.returncode:
            # Keep diagnostics in memory only; never log ASR output or file metadata.
            raise SubloomError(f"{Path(args[0]).name} failed (exit {proc.returncode}).\n{result[-3500:]}")
        return result
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        # Drain a blocked producer before closing its pipe.
        while reader.is_alive():
            try:
                messages.get(timeout=0.1)
            except queue.Empty:
                pass
        proc.stdout.close()
