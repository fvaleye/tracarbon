import asyncio
import datetime
from threading import Barrier
from threading import Event
from threading import Thread
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
from tracarbon.exporters import JSONExporter
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
    clock.monotonic.side_effect = [0.0, 30.0, 60.0, 3600.0, 3630.0, 3660.0]
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


def test_stop_collects_a_short_job_once(mocker):
    location = Country(name="fr", co2g_kwh=400.0)
    sensor = mocker.patch.object(
        MacEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(host_energy_usage=100.0)
    )
    clock = mock.Mock()
    clock.monotonic.return_value = 0.0
    mocker.patch.object(carbon_emissions, "time", clock)
    carbon = CarbonEmission(location=location, energy_consumption=MacEnergyConsumption())
    exporter = StdoutExporter(metric_generators=[CarbonEmissionGenerator(location=location, carbon_emission=carbon)])
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(interval_in_seconds=3600), exporter=exporter, location=location
    )

    try:
        assert tracarbon.stop() is None
        assert sensor.call_count == 0
        with tracarbon:
            clock.monotonic.return_value = 30.0

        assert tracarbon.report.total_co2g == pytest.approx(1 / 3)
        assert tracarbon.stop() == pytest.approx(1 / 3)
        assert sensor.call_count == 2
    finally:
        exporter.stop()


def test_stop_from_a_running_event_loop_collects_once_and_allows_a_stop_callback():
    readings = []

    async def sample() -> float:
        readings.append(1.0)
        if len(readings) == 2:
            tracarbon.stop()
        return 1.0

    exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=sample)])])
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(interval_in_seconds=3600),
        exporter=exporter,
        location=Country(name="fr", co2g_kwh=74.0),
    )

    async def stop() -> None:
        tracarbon.stop()

    try:
        tracarbon.start()
        asyncio.run(stop())
        assert readings == [1.0, 1.0]
        assert tracarbon.report.metric_report["sample"].call_count == 2
    finally:
        exporter.stop()


@pytest.mark.parametrize("workload_fails", [False, True])
def test_context_exit_preserves_workload_errors_when_final_collection_fails(mocker, tmp_path, workload_fails):
    workload_error = RuntimeError("workload failed")
    sampling_error = ValueError("sample failed")
    sample = mocker.AsyncMock(side_effect=[1.0, sampling_error])
    exporter = JSONExporter(
        path=str(tmp_path / "metrics.json"),
        metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=sample)])],
    )
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(interval_in_seconds=3600),
        exporter=exporter,
        location=Country(name="fr", co2g_kwh=74.0),
    )
    try:
        with pytest.raises((RuntimeError, ValueError)) as raised:
            with tracarbon:
                if workload_fails:
                    raise workload_error
        assert raised.value is (workload_error if workload_fails else sampling_error)
        assert tracarbon.report.end_time is not None
        assert tracarbon.report.metric_report["sample"].call_count == 1
    finally:
        exporter.stop()
        exporter.flush()


def test_concurrent_stops_share_a_final_sample_that_can_stop_from_its_callback():
    stopping = Barrier(3)
    readings = []
    errors = []

    async def sample() -> float:
        readings.append(1.0)
        if len(readings) == 2:
            tracarbon.stop()
            with pytest.raises(RuntimeError, match="collection callback"):
                tracarbon.start()
        return 1.0

    exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=sample)])])
    tracarbon = Tracarbon(
        configuration=TracarbonConfiguration(interval_in_seconds=3600),
        exporter=exporter,
        location=Country(name="fr", co2g_kwh=74.0),
    )

    def stop() -> None:
        try:
            stopping.wait(timeout=2)
            tracarbon.stop()
        except Exception as error:
            errors.append(error)

    threads = [Thread(target=stop, daemon=True) for _ in range(2)]
    try:
        tracarbon.start()
        for thread in threads:
            thread.start()
        stopping.wait(timeout=2)
    finally:
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=2)
        exporter.stop()

    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert readings == [1.0, 1.0]
    assert tracarbon.report.metric_report["sample"].call_count == 2


def test_stop_reads_the_closing_interval_after_an_active_collection(mocker):
    collecting = Event()
    release_sample = Event()
    stop_requested = Event()
    readings = []

    async def intensity() -> float:
        readings.append(400.0)
        if len(readings) == 2:
            collecting.set()
            release_sample.wait(timeout=2)
        return 400.0

    location = Country(name="fr", co2g_kwh=400.0)
    mocker.patch.object(Country, "get_latest_co2g_kwh", side_effect=intensity)
    mocker.patch.object(MacEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(host_energy_usage=100.0))
    clock = mock.Mock()
    clock.monotonic.side_effect = [0.0, 30.0, 60.0]
    mocker.patch.object(carbon_emissions, "time", clock)
    carbon = CarbonEmission(location=location, energy_consumption=MacEnergyConsumption())
    exporter = StdoutExporter(metric_generators=[CarbonEmissionGenerator(location=location, carbon_emission=carbon)])
    configuration = TracarbonConfiguration()
    configuration.interval_in_seconds = 0
    tracarbon = Tracarbon(configuration=configuration, exporter=exporter, location=location)
    stopper = Thread(target=tracarbon.stop, daemon=True)

    try:
        tracarbon.start()
        assert collecting.wait(timeout=2)
        set_stop_event = exporter.event.set

        def request_stop() -> None:
            set_stop_event()
            stop_requested.set()

        mocker.patch.object(exporter.event, "set", side_effect=request_stop)
        stopper.start()
        assert stop_requested.wait(timeout=2)
    finally:
        release_sample.set()
        if stopper.ident is not None:
            stopper.join(timeout=2)
        exporter.stop()

    assert not stopper.is_alive()
    assert readings == [400.0, 400.0, 400.0]
    assert tracarbon.report.total_co2g == pytest.approx(2 / 3)


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

    mocker.patch.object(StdoutExporter, "finish", side_effect=finish_collection)

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
