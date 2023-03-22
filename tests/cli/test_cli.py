import pytest
from kubernetes import config

from tracarbon import Country, EnergyUsage, Kubernetes, MacEnergyConsumption
from tracarbon.cli import get_exporter, run_metrics
from tracarbon.exporters import DatadogExporter, StdoutExporter
from tracarbon.hardwares import Container, Pod


def test_get_exporter_by_name():
    stdout_exporter = get_exporter(exporter_name="Stdout", metric_generators=[])
    datadadog_exporter = get_exporter(exporter_name="Datadog", metric_generators=[])

    assert isinstance(stdout_exporter, StdoutExporter) is True
    assert isinstance(datadadog_exporter, DatadogExporter) is True


def test_get_exporter_by_name_should_raise_error():
    with pytest.raises(ValueError) as exception:
        get_exporter(exporter_name="unknown", metric_generators=[])

    assert "This exporter is not available in the list:" in exception.value.args[0]


@pytest.mark.darwin
def test_run_metrics_should_be_ok(mocker, caplog):
    exporter = "Stdout"
    mocker.patch.object(
        Country,
        "get_location",
        return_value=Country(name="fr", co2g_kwh=50.0),
    )
    energy_usage = EnergyUsage(host_energy_usage=60.0)
    mocker.patch.object(config, "load_kube_config", return_value=None)
    mocker.patch.object(
        MacEnergyConsumption, "get_energy_usage", return_value=energy_usage
    )

    run_metrics(exporter_name=exporter, running=False)

    assert "Metric name[test.carbon_emission_host]" in caplog.text
    assert "Metric name[test.energy_consumption_host]" in caplog.text
    assert "units:co2g/kwh" in caplog.text
    assert "units:watts" in caplog.text

    energy_usage = EnergyUsage(cpu_energy_usage=15.0, memory_energy_usage=12.0)
    mocker.patch.object(
        MacEnergyConsumption, "get_energy_usage", return_value=energy_usage
    )
    mocker.patch.object(
        Kubernetes,
        "get_pods_usage",
        return_value=[
            Pod(
                name="pod_name",
                namespace="default",
                containers=[
                    Container(name="container_name", cpu_usage="1", memory_usage=2)
                ],
            )
        ],
    )

    run_metrics(exporter_name=exporter, running=False, containers=True)

    assert "Metric name[test.carbon_emission_kubernetes_total]" in caplog.text
    assert "Metric name[test.energy_consumption_kubernetes_total]" in caplog.text
    assert "units:co2mg/kwh" in caplog.text
    assert "units:milliwatts" in caplog.text
