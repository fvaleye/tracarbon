import os
import subprocess
import sys

import pytest
from _pytest.logging import LogCaptureFixture
from loguru import logger


def test_some_interaction(monkeypatch):
    monkeypatch.setattr("os.getcwd", lambda: "/")


ALL = set("darwin linux windows".split())


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
def caplog(caplog: LogCaptureFixture):
    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


def pytest_runtest_setup(item):
    supported_platforms = ALL.intersection(mark.name for mark in item.iter_markers())
    plat = sys.platform
    if supported_platforms and plat not in supported_platforms:
        pytest.skip(f"cannot run on platform {plat}")
