import os
import platform
import subprocess
import sys
from threading import Timer

import pytest
from loguru import logger

PLATFORMS = {"darwin", "linux", "windows"}


@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    """Remove requests.sessions.Session.request for all tests."""
    monkeypatch.delattr("requests.sessions.Session.request")


@pytest.fixture
def run_python(tmp_path):
    def run(*arguments: str, **environment: str) -> str:
        inherited_environment = {name: value for name, value in os.environ.items() if not name.startswith("TRACARBON_")}
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=tmp_path,
            env={**inherited_environment, "KUBECONFIG": os.devnull, **environment},
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stderr

    return run


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture):
    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


@pytest.fixture
def instant_timer(mocker):
    mocker.patch("tracarbon.exporters.exporter.Timer", side_effect=lambda _interval, *args: Timer(0, *args))


def pytest_runtest_setup(item):
    supported_platforms = PLATFORMS.intersection(mark.name for mark in item.iter_markers())
    platform_name = platform.system().lower()
    if supported_platforms and platform_name not in supported_platforms:
        pytest.skip(f"cannot run on platform {platform_name}")
