import os

from loguru import logger

from tracarbon.conf import TracarbonConfiguration
from tracarbon.conf import check_optional_dependency


def test_a_missing_optional_dependency_is_not_logged(caplog):
    assert check_optional_dependency(name="tracarbon_missing_optional_dependency") is False
    assert caplog.text == ""


def test_configuration_keeps_the_host_logger_handlers():
    host_messages = []
    host_handler_id = logger.add(host_messages.append, format="{message}")

    TracarbonConfiguration()
    logger.info("host message")

    assert host_messages == ["host message\n"]
    logger.remove(host_handler_id)


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


def test_configuration_replaces_the_default_loguru_handler_with_the_tracarbon_one(run_python):
    script = (
        "from loguru import logger; from tracarbon import TracarbonConfiguration; "
        "TracarbonConfiguration(); logger.debug('debug line'); logger.info('info line')"
    )

    logged = run_python("-c", script)

    assert "| INFO     info line" in logged
    assert "debug line" not in logged


def test_configuration_keeps_the_handlers_of_a_host_that_configured_loguru(run_python):
    script = (
        "import sys; from loguru import logger; logger.remove(0); "
        "logger.add(sys.stderr, format='HOST {level} {message}', level='DEBUG'); "
        "from tracarbon import TracarbonConfiguration; TracarbonConfiguration(); logger.debug('debug line')"
    )

    assert run_python("-c", script) == "HOST DEBUG debug line\n"


def test_importing_tracarbon_leaves_loguru_untouched(run_python):
    script = "import tracarbon; from loguru import logger; logger.debug('debug line')"

    assert "| DEBUG    | __main__:<module>:1 - debug line" in run_python("-c", script)
