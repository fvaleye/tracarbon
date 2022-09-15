import pytest

from tracarbon import Country, MacEnergyConsumption
from tracarbon.cli import get_exporter, run_metrics
from tracarbon.exporters import DatadogExporter, StdoutExporter


def test_get_exporter_by_name():
    stdout_exporter = get_exporter(exporter_name="Stdout", metrics=[])
    datadadog_exporter = get_exporter(exporter_name="Datadog", metrics=[])

    assert isinstance(stdout_exporter, StdoutExporter) is True
    assert isinstance(datadadog_exporter, DatadogExporter) is True


def test_get_exporter_by_name_should_raise_error():

    with pytest.raises(ValueError) as exception:
        get_exporter(exporter_name="unknown", metrics=[])

    assert "This exporter is not available in the list:" in exception.value.args[0]


@pytest.mark.darwin
def test_run_metrics_should_be_ok(mocker, caplog):
    exporter = "Stdout"
    mocker.patch.object(
        Country,
        "get_location",
        return_value=Country(name="fr", co2g_kwh=50.0),
    )
    mocker.patch.object(MacEnergyConsumption, "run", return_value=60.0)

    run_metrics(exporter_name=exporter, running=False)

    assert "Metric name[test.co2_emission]" in caplog.text
    assert "Metric name[test.hardware_memory_usage]" in caplog.text
    assert "Metric name[test.hardware_cpu_usage]" in caplog.text
    assert "Metric name[test.energy_consumption]" in caplog.text
