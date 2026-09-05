import asyncio
import datetime
from unittest import mock

import pytest
from kubernetes import config

from tracarbon import CarbonEmission
from tracarbon import EnergyUsage
from tracarbon import MacEnergyConsumption
from tracarbon.builder import Tracarbon
from tracarbon.builder import TracarbonBuilder
from tracarbon.builder import TracarbonConfiguration
from tracarbon.builder import TracarbonReport
from tracarbon.emissions import carbon_emissions
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import MetricReport
from tracarbon.exporters import StdoutExporter
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.general_metrics import CarbonEmissionKubernetesGenerator
from tracarbon.hardwares.containers import Kubernetes
from tracarbon.locations import Country


def test_restart_opens_a_new_report_without_attributing_stopped_time(mocker):
    location = Country(name="fr", co2g_kwh=74.0)
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=74.0)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(host_energy_usage=60.0))
    clock = mock.Mock()
    clock.monotonic.side_effect = [0.0, 60.0, 3600.0, 3660.0]
    mocker.patch.object(carbon_emissions, "time", clock)
    carbon_emission = CarbonEmission(location=location, energy_consumption=MacEnergyConsumption())
    exporter = StdoutExporter(
        metric_generators=[CarbonEmissionGenerator(location=location, carbon_emission=carbon_emission)]
    )
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(interval_in_seconds=3600), exporter=exporter, location=location
    )

    try:
        tracarbon.start()
        asyncio.run(exporter._launch_all())
        assert tracarbon.stop() == pytest.approx(0.074)
        previous_report = tracarbon.report

        tracarbon.start()
        assert exporter.metric_report["carbon_emission_host"].total == 0.0
        assert tracarbon.report.end_time is None
        assert tracarbon.report.metric_report == {}
        asyncio.run(exporter._launch_all())
        assert tracarbon.stop() == pytest.approx(0.074)
        assert previous_report.total_co2g == pytest.approx(0.074)
        assert previous_report.end_time <= tracarbon.report.start_time
    finally:
        exporter.stop()


@pytest.mark.parametrize("generator_type", [CarbonEmissionGenerator, CarbonEmissionKubernetesGenerator])
def test_start_discards_a_carbon_measurement_from_before_the_run(mocker, generator_type):
    location = Country(name="fr", co2g_kwh=74.0)
    mocker.patch.object(Country, "get_latest_co2g_kwh", return_value=74.0)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(host_energy_usage=60.0))
    mocker.patch.object(config, "load_kube_config", return_value=None)
    mocker.patch.object(Kubernetes, "get_pods_usage", return_value=[])
    get_co2_usage = mocker.spy(CarbonEmission, "get_co2_usage")
    carbon_emission = CarbonEmission(
        location=location,
        energy_consumption=MacEnergyConsumption(),
        previous_energy_consumption_time=datetime.datetime.now() - datetime.timedelta(seconds=60),
    )
    exporter = StdoutExporter(metric_generators=[generator_type(location=location, carbon_emission=carbon_emission)])
    try:
        exporter.start(interval_in_seconds=3600)
    finally:
        exporter.stop()

    assert get_co2_usage.spy_return.host_carbon_usage == 0.0


def test_stop_publishes_the_report_after_collection_settles(mocker):
    exporter = StdoutExporter(metric_generators=[])
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(), exporter=exporter, location=Country(name="fr", co2g_kwh=74.0)
    )

    def finish_collection() -> None:
        assert tracarbon.report.end_time is None
        exporter.metric_report = {"carbon_emission_host": build_metric_report("carbon_emission_host", 4.2)}

    mocker.patch.object(StdoutExporter, "stop", side_effect=finish_collection)

    assert tracarbon.stop() == 4.2
    assert tracarbon.report.end_time is not None


def test_rejected_callback_restart_preserves_the_running_tracker():
    reports = []

    async def sample() -> float:
        reports.append(tracarbon.report)
        with pytest.raises(RuntimeError, match="collection callback"):
            tracarbon.start()
        return 1.0

    exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=sample)])])
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(interval_in_seconds=3600),
        exporter=exporter,
        location=Country(name="fr", co2g_kwh=74.0),
    )
    try:
        tracarbon.start()
        assert tracarbon.report is reports[0]
        assert not exporter.stopped
        assert exporter._timer is not None
        assert exporter.metric_report["sample"].call_count == 1
    finally:
        exporter.stop()


def build_metric_report(metric_name: str, total: float) -> MetricReport:
    async def metric_value() -> float:
        return total

    return MetricReport(
        exporter_name="Stdout",
        metric=Metric(name=metric_name, value=metric_value),
        total=total,
    )


@pytest.mark.darwin
def test_builder_without_configuration(mocker):
    location = "fr"
    mocker.patch.object(Country, "get_current_country", return_value=location)
    builder = TracarbonBuilder()
    expected_exporter = StdoutExporter(
        metric_generators=[CarbonEmissionGenerator(location=Country(name=location, co2g_kwh=74.0))]
    )

    tracarbon = builder.build()

    assert tracarbon.configuration == TracarbonConfiguration()
    assert type(tracarbon.exporter) is type(expected_exporter)
    assert type(tracarbon.exporter.metric_generators[0]) is type(expected_exporter.metric_generators[0])
    assert tracarbon.location == Country(name=location, co2g_kwh=74.0)


@pytest.mark.darwin
def test_builder_with_configuration():
    configuration = TracarbonConfiguration(co2signal_api_key="API_KEY")
    expected_location = Country(name="fr", co2g_kwh=74.0)
    expected_exporter = StdoutExporter(metric_generators=[CarbonEmissionGenerator(location=expected_location)])
    builder = TracarbonBuilder(configuration=configuration)

    tracarbon = builder.with_exporter(exporter=expected_exporter).with_location(location=expected_location).build()

    assert tracarbon.configuration == configuration
    assert tracarbon.location == expected_location
    assert tracarbon.exporter == expected_exporter
    assert tracarbon.report is not None


def test_report_total_co2g_reads_the_host_carbon_emission():
    report = TracarbonReport(metric_report={"carbon_emission_host": build_metric_report("carbon_emission_host", 12.5)})

    assert report.total_co2g == 12.5


def test_report_total_co2g_without_a_host_carbon_emission():
    report = TracarbonReport(
        metric_report={"energy_consumption_host": build_metric_report("energy_consumption_host", 30.0)}
    )

    assert report.total_co2g is None


def test_stop_returns_the_total_co2g_emitted():
    exporter = StdoutExporter(metric_generators=[])
    exporter.metric_report = {"carbon_emission_host": build_metric_report("carbon_emission_host", 4.2)}
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(),
        exporter=exporter,
        location=Country(name="fr", co2g_kwh=74.0),
    )

    total_co2g = tracarbon.stop()

    assert total_co2g == 4.2
