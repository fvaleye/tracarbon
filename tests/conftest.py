import sys

import pytest
import requests
from _pytest.logging import LogCaptureFixture
from dotenv import load_dotenv
from loguru import logger

ALL = set("darwin linux windows".split())


load_dotenv()


@pytest.fixture
def not_ec2_mock(mocker):
    mocker.patch.object(
        requests,
        "head",
        side_effect=ValueError(),
    )


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
