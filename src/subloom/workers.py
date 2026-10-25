from collections.abc import Callable
import time
from PySide6.QtCore import QObject, QThread, Signal

from .errors import Cancelled, GPUError
from .process import Cancellation


class Job(QThread):
    progress = Signal(str, object)
    succeeded = Signal(object)
    failed = Signal(str, str)

    def __init__(self, function: Callable, parent: QObject | None = None):
        super().__init__(parent)
        self.function = function
        self.cancellation = Cancellation()

    def run(self) -> None:
        last_update = 0.0
        last_step = ""

        def progress(step, value):
            nonlocal last_update, last_step
            now = time.monotonic()
            # Hashing multi-GB models must not flood Qt's queued UI events.
            if step != last_step or now - last_update >= 0.08 or value == 1.0:
                self.progress.emit(step, value)
                last_update, last_step = now, step
        try:
            self.succeeded.emit(self.function(self.cancellation, progress))
        except Cancelled as exc:
            self.failed.emit("cancel", str(exc))
        except GPUError as exc:
            self.failed.emit("gpu", str(exc))
        except Exception as exc:
            self.failed.emit("error", str(exc))
        # QThread.finished is emitted by Qt after run returns. The controller
        # joins native cleanup before deleting this single owned job object.

    def cancel(self) -> None:
        self.cancellation.cancel()
