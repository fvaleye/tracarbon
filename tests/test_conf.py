import os
import sys

import pytest
from loguru import logger

from tracarbon.conf import TracarbonConfiguration
from tracarbon.conf import check_optional_dependency
from tracarbon.conf import logger_configuration


def test_a_missing_optional_dependency_is_not_logged(caplog):
    assert check_optional_dependency(name="tracarbon_missing_optional_dependency") is False
    assert caplog.text == ""


def test_configuration_reads_the_env_file_of_the_working_directory(mocker, monkeypatch, tmp_path):
    mocker.patch.dict(os.environ)
    os.environ.pop("TRACARBON_METRIC_PREFIX_NAME", None)
    (tmp_path / ".env").write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")
    monkeypatch.chdir(tmp_path)

    assert TracarbonConfiguration().metric_prefix_name == "from_env_file"


def test_configuration_keeps_the_variables_already_set(mocker, monkeypatch, tmp_path):
    mocker.patch.dict(os.environ, {"TRACARBON_METRIC_PREFIX_NAME": "from_environment"})
    (tmp_path / ".env").write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")
    monkeypatch.chdir(tmp_path)

    assert TracarbonConfiguration().metric_prefix_name == "from_environment"


def test_configuration_ignores_the_env_file_next_to_the_package(mocker, monkeypatch, tmp_path):
    mocker.patch.dict(os.environ)
    os.environ.pop("TRACARBON_METRIC_PREFIX_NAME", None)
    monkeypatch.chdir(tmp_path)

    assert TracarbonConfiguration().metric_prefix_name == "tracarbon"


def test_importing_tracarbon_leaves_the_environment_untouched(run_python, tmp_path):
    (tmp_path / ".env").write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")
    read_after_import = "import os, sys, tracarbon; sys.stderr.write(str(os.getenv('TRACARBON_METRIC_PREFIX_NAME')))"

    assert run_python("-c", read_after_import) == "None"


def test_configuration_loads_the_given_env_file(mocker, tmp_path):
    mocker.patch.dict(os.environ)
    os.environ.pop("TRACARBON_METRIC_PREFIX_NAME", None)
    env_file = tmp_path / "tracarbon.env"
    env_file.write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")

    assert TracarbonConfiguration(env_file_path=str(env_file)).metric_prefix_name == "from_env_file"


def test_configuration_keeps_the_api_key_out_of_its_repr():
    assert "SECRET_API_KEY" not in repr(TracarbonConfiguration(co2signal_api_key="SECRET_API_KEY"))


def test_logger_configuration_keeps_local_variables_out_of_tracebacks(capsys):
    logger_configuration(level="INFO")
    api_key = "SECRET_API_KEY"
    try:
        {"auth-token": api_key}["missing"]
    except KeyError:
        logger.exception("Request failed")
    finally:
        logger.remove()
        logger.add(sys.__stderr__)

    logged = capsys.readouterr().err
    assert "KeyError" in logged
    assert "SECRET_API_KEY" not in logged


def test_configuration_keeps_the_default_loguru_handler(run_python):
    script = (
        "from loguru import logger; from tracarbon import TracarbonConfiguration; "
        "TracarbonConfiguration(log_level='ERROR'); logger.debug('debug line')"
    )

    logged = run_python("-c", script)

    assert "| DEBUG    | __main__:<module>:1 - debug line" in logged


@pytest.mark.parametrize("autoinit", ["True", "False"])
def test_configuration_keeps_the_handlers_of_a_host_that_configured_loguru(run_python, tmp_path, autoinit):
    (tmp_path / ".env").write_text("LOGURU_AUTOINIT=True\n")
    script = """
import os
import sys
from loguru import logger

logger.remove()
logger.add(sys.stderr, format="HOST {level} {message}", level="DEBUG")
del os.environ["LOGURU_AUTOINIT"]
from tracarbon import TracarbonConfiguration

TracarbonConfiguration()
logger.debug("debug line")
"""

    assert run_python("-c", script, LOGURU_AUTOINIT=autoinit) == "HOST DEBUG debug line\n"
