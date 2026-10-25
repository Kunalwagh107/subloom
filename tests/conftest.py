import os
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_configure(config):
    # pytest creates basetemp itself, but does not create missing parents.
    # .test-data is intentionally absent from a clean source checkout.
    basetemp = config.getoption("basetemp")
    if basetemp:
        Path(basetemp).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def cancel():
    from subloom.process import Cancellation
    return Cancellation()


@pytest.fixture
def ffmpeg():
    from subloom.media import executable
    try:
        return executable("ffmpeg")
    except Exception:
        pytest.skip("Install pinned FFmpeg runtime with scripts/bootstrap_runtime.py")


@pytest.fixture(scope="session")
def speech_corpus():
    return Path(os.environ.get("SUBLOOM_TEST_CORPUS", ".test-data/corpus")).resolve()


@pytest.fixture(scope="session")
def model_dir():
    path = Path(os.environ.get("SUBLOOM_TEST_MODELS", ".test-data/models"))
    from subloom.models import ModelManager
    if not any(ModelManager(path).installed(model) for model in ("base", "small", "medium")):
        pytest.skip("Actual ASR requires an explicitly downloaded multilingual model")
    return path.resolve()
