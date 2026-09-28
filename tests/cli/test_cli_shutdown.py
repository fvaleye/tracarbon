import signal

import pytest
from typer.testing import CliRunner

from tracarbon import Country
from tracarbon import EnergyConsumption
from tracarbon import EnergyUsage
from tracarbon.cli import app
from tracarbon.exporters import JSONExporter
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import StdoutExporter
from tracarbon.hardwares import WindowsEnergyConsumption


@pytest.mark.darwin
@pytest.mark.linux
def test_run_writes_the_final_report_on_sigterm(mocker, caplog):
    mocker.patch.object(Country, "get_location", return_value=Country.from_file("fr"))
    mocker.patch.object(EnergyConsumption, "from_platform", return_value=WindowsEnergyConsumption())
    mocker.patch.object(WindowsEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(gpu_energy_usage=10.0))
    mocker.patch("tracarbon.cli.time", **{"sleep.side_effect": lambda _: signal.raise_signal(signal.SIGTERM)})

    def terminate_like_the_default_action(signum, frame):
        raise SystemExit(128 + signum)

    previous_sigterm_handler = signal.signal(signal.SIGTERM, terminate_like_the_default_action)
    try:
        result = CliRunner().invoke(app, ["run"])
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm_handler)

    assert result.exit_code == 0
    assert "Total CO2 emitted" in caplog.text


@pytest.mark.darwin
@pytest.mark.linux
@pytest.mark.parametrize("shutdown_signal", [signal.SIGINT, signal.SIGTERM])
def test_run_exits_with_an_error_when_final_collection_fails(mocker, tmp_path, shutdown_signal):
    readings = []

    async def sample() -> float:
        readings.append(1.0)
        if len(readings) > 1:
            raise OSError("final collection failed")
        return 1.0

    exporter = JSONExporter(
        path=str(tmp_path / "metrics.json"),
        metric_generators=[MetricGenerator(metrics=[Metric(name="carbon_emission_host", value=sample)])],
    )
    mocker.patch.object(Country, "get_location", return_value=Country.from_file("fr"))
    mocker.patch("tracarbon.cli.get_exporter", return_value=exporter)
    mocker.patch("tracarbon.cli.time", **{"sleep.side_effect": lambda _: signal.raise_signal(shutdown_signal)})

    previous_sigint_handler = signal.signal(signal.SIGINT, signal.default_int_handler)
    previous_sigterm_handler = signal.getsignal(signal.SIGTERM)
    try:
        result = CliRunner().invoke(app, ["run"])
    finally:
        exporter.stop()
        signal.signal(signal.SIGINT, previous_sigint_handler)
        signal.signal(signal.SIGTERM, previous_sigterm_handler)

    assert readings == [1.0, 1.0]
    assert result.exit_code == 1


def test_run_exits_with_an_error_when_initialization_fails(mocker):
    mocker.patch.object(Country, "get_location", return_value=Country.from_file("fr"))
    mocker.patch("tracarbon.cli.signal")

    result = CliRunner().invoke(app, ["run", "--exporter-name", "Nope"])

    assert result.exit_code == 1


def test_run_exits_with_an_error_when_first_collection_fails(mocker):
    async def fail_collection(self, metric_generator):
        raise OSError("sensor unavailable")

    mocker.patch.object(Country, "get_location", return_value=Country.from_file("fr"))
    mocker.patch.object(StdoutExporter, "launch", fail_collection)
    mocker.patch("tracarbon.cli.signal")

    result = CliRunner().invoke(app, ["run"])

    assert result.exit_code == 1
