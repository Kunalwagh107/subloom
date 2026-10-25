import os
import sys
from pathlib import Path


def data_dir() -> Path:
    if os.environ.get("SUBLOOM_DATA_DIR"):
        root = Path(os.environ["SUBLOOM_DATA_DIR"]).expanduser()
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Subloom"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "subloom"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def tools_dir() -> Path:
    if os.environ.get("SUBLOOM_TOOLS_DIR"):
        return Path(os.environ["SUBLOOM_TOOLS_DIR"])
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "tools"
    return Path(__file__).resolve().parents[2] / ".tools" / "runtime"
