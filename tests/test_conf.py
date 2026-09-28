import os
import sys

import pytest
from loguru import logger

from tracarbon.conf import TracarbonConfiguration
from tracarbon.conf import check_optional_dependency
from tracarbon.conf import logger_configuration


def test_missing_optional_dependency_does_not_log(caplog):
    assert check_optional_dependency(name="tracarbon_missing_optional_dependency") is False
    assert caplog.text == ""


def test_configuration_loads_working_directory_env_file(mocker, monkeypatch, tmp_path):
    mocker.patch.dict(os.environ)
    os.environ.pop("TRACARBON_METRIC_PREFIX_NAME", None)
    (tmp_path / ".env").write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")
    monkeypatch.chdir(tmp_path)

    assert TracarbonConfiguration().metric_prefix_name == "from_env_file"


def test_environment_overrides_env_file(mocker, monkeypatch, tmp_path):
    mocker.patch.dict(os.environ, {"TRACARBON_METRIC_PREFIX_NAME": "from_environment"})
    (tmp_path / ".env").write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")
    monkeypatch.chdir(tmp_path)

    assert TracarbonConfiguration().metric_prefix_name == "from_environment"


def test_configuration_ignores_package_env_file(mocker, monkeypatch, tmp_path):
    mocker.patch.dict(os.environ)
    os.environ.pop("TRACARBON_METRIC_PREFIX_NAME", None)
    monkeypatch.chdir(tmp_path)

    assert TracarbonConfiguration().metric_prefix_name == "tracarbon"


def test_import_does_not_load_env_file(run_python, tmp_path):
    (tmp_path / ".env").write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")
    read_after_import = "import os, sys, tracarbon; sys.stderr.write(str(os.getenv('TRACARBON_METRIC_PREFIX_NAME')))"

    assert run_python("-c", read_after_import) == "None"


def test_configuration_loads_explicit_env_file(mocker, tmp_path):
    mocker.patch.dict(os.environ)
    os.environ.pop("TRACARBON_METRIC_PREFIX_NAME", None)
    env_file = tmp_path / "tracarbon.env"
    env_file.write_text("TRACARBON_METRIC_PREFIX_NAME=from_env_file\n")

    assert TracarbonConfiguration(env_file_path=str(env_file)).metric_prefix_name == "from_env_file"


def test_configuration_repr_hides_api_key(monkeypatch):
    monkeypatch.setenv("TRACARBON_CO2SIGNAL_API_KEY", "SECRET_API_KEY")

    assert "SECRET_API_KEY" not in repr(TracarbonConfiguration())


def test_logger_configuration_hides_traceback_locals(capsys):
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


def test_configuration_preserves_default_loguru_handler(run_python):
    script = (
        "from loguru import logger; from tracarbon import TracarbonConfiguration; "
        "TracarbonConfiguration(log_level='ERROR'); logger.debug('debug line')"
    )

    logged = run_python("-c", script)

    assert "debug line" in logged


@pytest.mark.parametrize("autoinit", ["True", "False"])
def test_configuration_preserves_host_loguru_handler(run_python, tmp_path, autoinit):
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
