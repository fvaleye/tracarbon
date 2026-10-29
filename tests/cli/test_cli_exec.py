import json
import os
import signal
import sys

import pytest
from typer.testing import CliRunner
from typer.testing import Result

from tracarbon import Country
from tracarbon import EnergyConsumption
from tracarbon import EnergyUsage
from tracarbon.cli import app
from tracarbon.exporters import StdoutExporter
from tracarbon.hardwares import WindowsEnergyConsumption

_MARK_THAT_IT_RAN = "import pathlib, sys; pathlib.Path(sys.argv[1]).touch()"


def _exec_python(code: str, *arguments: str, options: tuple[str, ...] = ()) -> Result:
    return CliRunner().invoke(app, ["exec", *options, "--", sys.executable, "-c", code, *arguments])


@pytest.fixture
def measured_host(mocker):
    mocker.patch.object(Country, "get_location", return_value=Country.from_file("fr"))
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=WindowsEnergyConsumption())
    mocker.patch.object(WindowsEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(host_energy_usage=10.0))


def test_exec_runs_the_command_as_given_and_exits_with_its_status(measured_host, tmp_path):
    report, received = tmp_path / "report.json", tmp_path / "received.txt"
    argument = "two words; $HOME"

    result = _exec_python(
        "import pathlib, sys; pathlib.Path(sys.argv[1]).write_text(sys.argv[2]); sys.exit(3)",
        str(received),
        argument,
        options=("--output", str(report)),
    )

    assert result.exit_code == 3
    assert received.read_text() == argument
    assert json.loads(report.read_text())["metric_report"]["energy_consumption_host"]["total"] > 0
    assert "memory: unavailable" in result.output


@pytest.mark.parametrize(
    ("command", "status"),
    [(["tracarbon-missing-command"], 127), ([__file__], 126)],
    ids=["missing", "not_executable"],
)
def test_exec_exits_like_a_shell_when_the_command_cannot_run(measured_host, command, status):
    assert CliRunner().invoke(app, ["exec", "--", *command]).exit_code == status


@pytest.mark.darwin
@pytest.mark.linux
def test_exec_exits_126_when_the_script_interpreter_is_missing(measured_host, tmp_path):
    script = tmp_path / "script"
    script.write_text("#!/nonexistent/interpreter\n")
    script.chmod(0o755)

    assert CliRunner().invoke(app, ["exec", "--", str(script)]).exit_code == 126


def test_exec_keeps_dotenv_settings_out_of_the_command(measured_host, mocker, monkeypatch, tmp_path):
    mocker.patch.dict(os.environ)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("TRACARBON_TEST_SECRET=leaked\n")
    received = tmp_path / "received.txt"

    result = _exec_python(
        "import os, pathlib, sys; pathlib.Path(sys.argv[1]).write_text(os.environ.get('TRACARBON_TEST_SECRET', ''))",
        str(received),
    )

    assert result.exit_code == 0
    assert received.read_text() == ""


@pytest.mark.darwin
@pytest.mark.linux
def test_exec_exits_with_128_plus_the_signal_that_killed_the_command(measured_host):
    result = _exec_python("import os, signal; os.kill(os.getpid(), signal.SIGKILL)")

    assert result.exit_code == 128 + signal.SIGKILL


def test_exec_refuses_to_overwrite_a_report(measured_host, tmp_path):
    report, ran = tmp_path / "report.json", tmp_path / "ran"
    report.write_text("{}")

    result = _exec_python(_MARK_THAT_IT_RAN, str(ran), options=("--output", str(report)))

    assert result.exit_code == 1
    assert report.read_text() == "{}"
    assert not ran.exists()


def test_exec_does_not_run_the_command_when_measurement_cannot_start(measured_host, mocker, tmp_path):
    mocker.patch.object(WindowsEnergyConsumption, "get_energy_usage", side_effect=OSError("sensor unavailable"))
    ran = tmp_path / "ran"

    result = _exec_python(_MARK_THAT_IT_RAN, str(ran))

    assert result.exit_code == 1
    assert not ran.exists()


@pytest.mark.darwin
@pytest.mark.linux
def test_exec_keeps_the_command_immune_to_hangups_under_nohup(measured_host, tmp_path):
    received = tmp_path / "sighup.txt"
    command = "import pathlib, signal, sys; pathlib.Path(sys.argv[1]).write_text(str(signal.getsignal(signal.SIGHUP)))"
    previous_sighup_handler = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        result = CliRunner().invoke(app, ["exec", sys.executable, "-c", command, str(received)])
    finally:
        signal.signal(signal.SIGHUP, previous_sighup_handler)

    assert result.exit_code == 0
    assert received.read_text() == str(signal.SIG_IGN)


@pytest.mark.parametrize(("command_status", "status"), [(0, 1), (3, 3)], ids=["command_succeeded", "command_failed"])
def test_exec_keeps_the_measurement_and_the_command_status_when_the_final_reading_fails(
    measured_host, mocker, tmp_path, command_status, status
):
    def fail_after_stopping(exporter):
        exporter.stop()
        raise OSError("final collection failed")

    mocker.patch.object(StdoutExporter, "finish", fail_after_stopping)
    report = tmp_path / "report.json"

    result = _exec_python(f"raise SystemExit({command_status})", options=("--output", str(report)))

    assert result.exit_code == status
    assert "energy_consumption_host" in json.loads(report.read_text())["metric_report"]


@pytest.mark.darwin
@pytest.mark.linux
@pytest.mark.parametrize(
    ("command", "status"),
    [
        ("import os, signal; os.kill(os.getppid(), signal.SIGINT); os.kill(os.getpid(), signal.SIGINT)", 130),
        ("import os, signal, time; os.kill(os.getppid(), signal.SIGTERM); time.sleep(10)", 143),
    ],
    ids=["ctrl_c_reaches_tracarbon_and_the_command", "sigterm_reaches_tracarbon"],
)
def test_exec_keeps_measuring_until_a_stopped_command_exits(measured_host, command, status):
    previous_sigterm_handler = signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        result = _exec_python(command)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm_handler)

    assert result.exit_code == status
    assert "host: " in result.output
