import sys

import pytest
from _pytest.logging import LogCaptureFixture
from dotenv import load_dotenv
from loguru import logger


def test_some_interaction(monkeypatch):
    monkeypatch.setattr("os.getcwd", lambda: "/")


ALL = set("darwin linux windows".split())


load_dotenv()


@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    """Remove requests.sessions.Session.request for all tests."""
    monkeypatch.delattr("requests.sessions.Session.request")


@pytest.fixture
def caplog(caplog: LogCaptureFixture):
    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


def pytest_runtest_setup(item):
    supported_platforms = ALL.intersection(mark.name for mark in item.iter_markers())
    plat = sys.platform
    if supported_platforms and plat not in supported_platforms:
        pytest.skip("cannot run on platform {}".format(plat))
