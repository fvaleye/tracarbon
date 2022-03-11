import os
import sys

import pytest
from _pytest.logging import LogCaptureFixture
from loguru import logger

ALL = set("darwin linux windows".split())

# Deactivate aiocache for the test
os.environ["AIOCACHE_DISABLE"] = "1"
os.environ["TRACARBON_INTERVAL_IN_SECONDS"] = "1"


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
