import asyncio
import sys
from functools import partial
from typing import Iterator
from unittest.mock import AsyncMock

import psutil
import pytest
from prometheus_client import REGISTRY
from prometheus_client import CollectorRegistry
from prometheus_client import Counter
from prometheus_client import Gauge
from pytest_mock import MockerFixture

from tracarbon import Country
from tracarbon import EnergyUsage
from tracarbon import Kubernetes
from tracarbon import MacEnergyConsumption
from tracarbon import MetricGenerator
from tracarbon.exporters import Metric
from tracarbon.exporters import PrometheusExporter
from tracarbon.exporters import Tag
from tracarbon.general_metrics import EnergyConsumptionKubernetesGenerator
from tracarbon.hardwares import Container
from tracarbon.hardwares import Pod


def test_prometheus_exporter(mocker):
    mocker.patch("tracarbon.exporters.prometheus_exporter.start_http_server")
    interval_in_seconds = 1
    memory_value = 70
    mock_memory_value = ["0", "0", memory_value]
    mocker.patch.object(psutil, "virtual_memory", return_value=mock_memory_value)
    zero_value = 0
    expected_metric_1 = "gauge:tracarbon_test_metric_1"

    async def get_memory_usage() -> float:
        return psutil.virtual_memory()[2]

    async def get_zero_value() -> float:
        return zero_value

    mocker.patch.object(
        Country,
        "get_location",
        return_value=Country(name="fr", co2g_kwh=50.0),
    )
    memory_metric = Metric(
        name="test_metric_1",
        value=get_memory_usage,
        tags=[Tag(key="test", value="tags")],
    )
    zero_metric = Metric(
        name="zero_metric",
        value=get_zero_value,
        tags=[Tag(key="test", value="tags")],
    )
    metric_generators = [MetricGenerator(metrics=[memory_metric, zero_metric])]
    exporter = PrometheusExporter(
        quit=True,
        metric_generators=metric_generators,
        metric_prefix_name="tracarbon",
        address="127.0.0.1",
    )
    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    assert str(exporter.prometheus_metrics["tracarbon_test_metric_1"]) == expected_metric_1
    assert exporter.metric_report["test_metric_1"].exporter_name == PrometheusExporter.get_name()
    assert exporter.metric_report["test_metric_1"].metric == memory_metric
    assert exporter.metric_report["test_metric_1"].total > 0
    assert exporter.metric_report["test_metric_1"].average > 0
    assert exporter.metric_report["test_metric_1"].minimum < sys.float_info.max
    assert exporter.metric_report["test_metric_1"].maximum > 0
    assert exporter.metric_report["test_metric_1"].call_count == 1
    assert exporter.metric_report["zero_metric"].total == zero_value
    assert exporter.metric_report["zero_metric"].call_count == 1


def test_prometheus_preserves_default_gc_metrics(mocker):
    mocker.patch("tracarbon.exporters.prometheus_exporter.start_http_server")

    PrometheusExporter(metric_generators=[], address="127.0.0.1", port=0)

    assert REGISTRY.get_sample_value("python_gc_collections_total", {"generation": "0"}) is not None


@pytest.fixture
def prometheus_registry(mocker: MockerFixture) -> CollectorRegistry:
    registry = CollectorRegistry()
    mocker.patch("tracarbon.exporters.prometheus_exporter.start_http_server")
    mocker.patch("tracarbon.exporters.prometheus_exporter.Gauge", new=partial(Gauge, registry=registry))
    mocker.patch("tracarbon.exporters.prometheus_exporter.Counter", new=partial(Counter, registry=registry))
    mocker.patch.dict("tracarbon.exporters.prometheus_exporter._shared_metrics", clear=True)
    return registry


@pytest.mark.asyncio
async def test_prometheus_reuses_a_supplied_gauge(prometheus_registry: CollectorRegistry) -> None:
    gauge = Gauge("custom", "A supplied gauge", ["location"], registry=prometheus_registry)
    metric = Metric(name="custom", value=AsyncMock(return_value=7.0), tags=[Tag(key="location", value="fr")])
    exporter = PrometheusExporter(
        metric_generators=[MetricGenerator(metrics=[metric])], prometheus_metrics={"custom": gauge}
    )

    await exporter._launch_all()

    assert prometheus_registry.get_sample_value("custom", {"location": "fr"}) == 7.0
    assert exporter.prometheus_metrics["custom"] is gauge


@pytest.mark.asyncio
async def test_supplied_gauges_stay_in_their_own_registry(prometheus_registry: CollectorRegistry) -> None:
    supplied_registry = CollectorRegistry()
    gauge = Gauge("custom", "A supplied gauge", ["location"], registry=supplied_registry)
    metric = Metric(name="custom", value=AsyncMock(side_effect=[1.0, 2.0]), tags=[Tag(key="location", value="fr")])
    generator = MetricGenerator(metrics=[metric])
    first = PrometheusExporter(metric_generators=[generator], prometheus_metrics={"custom": gauge})
    second = PrometheusExporter(metric_generators=[generator])

    await first._launch_all()
    await second._launch_all()

    assert supplied_registry.get_sample_value("custom", {"location": "fr"}) == 1.0
    assert prometheus_registry.get_sample_value("custom", {"location": "fr"}) == 2.0


@pytest.mark.asyncio
async def test_prometheus_reuses_registered_metrics(
    prometheus_registry: CollectorRegistry,
) -> None:
    power = Metric(
        name="energy_consumption_host", value=AsyncMock(return_value=10.0), tags=[Tag(key="units", value="watts")]
    )
    await PrometheusExporter(metric_generators=[MetricGenerator(metrics=[power])])._launch_all()

    power.value = AsyncMock(return_value=12.0)
    await PrometheusExporter(metric_generators=[MetricGenerator(metrics=[power])])._launch_all()

    assert prometheus_registry.get_sample_value("energy_consumption_host", {"units": "watts"}) == 12.0


@pytest.mark.asyncio
async def test_prometheus_accumulates_grams_and_updates_gauges(
    prometheus_registry: CollectorRegistry,
) -> None:
    host_carbon = Metric(
        name="carbon_emission_host",
        value=AsyncMock(side_effect=[0.25, 0.75]),
        tags=[Tag(key="location", value="fr"), Tag(key="units", value="co2g")],
    )
    container_carbon = Metric(
        name="carbon_emission_kubernetes_total",
        value=AsyncMock(side_effect=[500.0, 250.0]),
        tags=[Tag(key="pod_name", value="app"), Tag(key="units", value="co2mg")],
    )
    host_power = Metric(
        name="energy_consumption_host",
        value=AsyncMock(side_effect=[10.0, 12.0]),
        tags=[Tag(key="location", value="fr"), Tag(key="units", value="watts")],
    )
    exporter = PrometheusExporter(
        metric_generators=[MetricGenerator(metrics=[host_carbon, container_carbon, host_power])],
        metric_prefix_name="tracarbon",
    )

    await exporter._launch_all()
    await exporter._launch_all()

    assert prometheus_registry.get_sample_value("tracarbon_carbon_emission_host_grams_total", {"location": "fr"}) == 1.0
    assert (
        prometheus_registry.get_sample_value("tracarbon_carbon_emission_kubernetes_grams_total", {"pod_name": "app"})
        == 0.75
    )
    assert (
        prometheus_registry.get_sample_value("tracarbon_energy_consumption_host", {"location": "fr", "units": "watts"})
        == 12.0
    )
    assert (
        prometheus_registry.get_sample_value("tracarbon_carbon_emission_host", {"location": "fr", "units": "co2g"})
        == 0.75
    )
    assert (
        prometheus_registry.get_sample_value(
            "tracarbon_carbon_emission_kubernetes_total", {"pod_name": "app", "units": "co2mg"}
        )
        == 250.0
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("second_has_collected", "initial_total", "final_total"), [(False, 1.0, 2.0), (True, 2.0, 3.0)]
)
async def test_prometheus_preserves_shared_counters_during_collection(
    prometheus_registry: CollectorRegistry, second_has_collected: bool, initial_total: float, final_total: float
) -> None:
    carbon = Metric(
        name="carbon_emission_kubernetes_cpu",
        value=AsyncMock(return_value=1.0),
        tags=[Tag(key="pod_name", value="app"), Tag(key="units", value="co2g")],
    )
    first_generator = MetricGenerator(metrics=[carbon])
    second_generator = MetricGenerator(metrics=[carbon])
    first = PrometheusExporter(metric_generators=[first_generator])
    second = PrometheusExporter(metric_generators=[second_generator])
    counter_name = "carbon_emission_kubernetes_cpu_grams_total"
    await first._launch_all()
    if second_has_collected:
        await second._launch_all()
    assert prometheus_registry.get_sample_value(counter_name, {"pod_name": "app"}) == initial_total

    async def collect_after_first_drops_pod() -> float:
        first_generator.metrics = []
        await first._launch_all()
        assert prometheus_registry.get_sample_value(counter_name, {"pod_name": "app"}) == initial_total
        return 1.0

    carbon.value = collect_after_first_drops_pod
    await second._launch_all()
    assert prometheus_registry.get_sample_value(counter_name, {"pod_name": "app"}) == final_total

    second_generator.metrics = []
    await second._launch_all()
    assert [sample for metric in prometheus_registry.collect() for sample in metric.samples] == []


@pytest.mark.parametrize("during_collection", [False, True], ids=["before_collection", "during_collection"])
def test_prometheus_preserves_shared_counters_during_final_collection(
    mocker: MockerFixture, prometheus_registry: CollectorRegistry, during_collection: bool
) -> None:
    carbon = Metric(
        name="carbon_emission_kubernetes_cpu",
        value=AsyncMock(return_value=1.0),
        tags=[Tag(key="pod_name", value="app"), Tag(key="units", value="co2g")],
    )
    first_generator = MetricGenerator(metrics=[carbon])
    first = PrometheusExporter(metric_generators=[first_generator])
    second = PrometheusExporter(metric_generators=[MetricGenerator(metrics=[carbon])])
    counter_name = "carbon_emission_kubernetes_cpu_grams_total"

    async def collect_after_first_finishes() -> float:
        first_generator.metrics = []
        await asyncio.to_thread(first.finish)
        return 1.0

    try:
        first.start(interval_in_seconds=3600)
        second.start(interval_in_seconds=3600)
        assert prometheus_registry.get_sample_value(counter_name, {"pod_name": "app"}) == 2.0

        if during_collection:
            carbon.value = collect_after_first_finishes
        else:
            stop = PrometheusExporter.stop

            def finish_first_after_stop(exporter: PrometheusExporter) -> None:
                stop(exporter)
                if exporter is second:
                    first_generator.metrics = []
                    first.finish()

            mocker.patch.object(PrometheusExporter, "stop", new=finish_first_after_stop)
        second.finish()

        assert prometheus_registry.get_sample_value(counter_name, {"pod_name": "app"}) == 3.0
    finally:
        first.stop()
        second.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_increment", [-1.0, float("nan"), float("inf")])
async def test_prometheus_skips_invalid_counter_increments(
    prometheus_registry: CollectorRegistry, invalid_increment: float
) -> None:
    carbon = Metric(
        name="carbon_emission_host",
        value=AsyncMock(side_effect=[invalid_increment, 2.0]),
        tags=[Tag(key="location", value="fr"), Tag(key="units", value="co2g")],
    )
    power = Metric(
        name="energy_consumption_host",
        value=AsyncMock(return_value=10.0),
        tags=[Tag(key="location", value="fr"), Tag(key="units", value="watts")],
    )
    exporter = PrometheusExporter(metric_generators=[MetricGenerator(metrics=[carbon, power])])

    await exporter._launch_all()
    assert prometheus_registry.get_sample_value("carbon_emission_host_grams_total", {"location": "fr"}) == 0.0
    assert prometheus_registry.get_sample_value("energy_consumption_host", {"location": "fr", "units": "watts"}) == 10.0

    await exporter._launch_all()
    assert prometheus_registry.get_sample_value("carbon_emission_host_grams_total", {"location": "fr"}) == 2.0


@pytest.mark.asyncio
async def test_prometheus_exports_unlabelled_metrics(prometheus_registry: CollectorRegistry) -> None:
    carbon_with_only_its_unit = Metric(
        name="carbon_emission_host", value=AsyncMock(return_value=0.5), tags=[Tag(key="units", value="co2g")]
    )
    tagless = Metric(name="custom", value=AsyncMock(return_value=7.0))
    exporter = PrometheusExporter(metric_generators=[MetricGenerator(metrics=[carbon_with_only_its_unit, tagless])])

    await exporter._launch_all()

    assert prometheus_registry.get_sample_value("carbon_emission_host_grams_total") == 0.5
    assert prometheus_registry.get_sample_value("custom") == 7.0


@pytest.mark.asyncio
async def test_prometheus_removes_missing_pods_after_all_generators(prometheus_registry: CollectorRegistry) -> None:
    gone, live, shared = [
        Metric(name="container_watts", value=AsyncMock(return_value=42.0), tags=[Tag(key="pod_name", value=name)])
        for name in ("gone", "live", "shared")
    ]
    custom = Metric(name="custom", value=AsyncMock(return_value=7.0), tags=[Tag(key="source", value="custom")])
    first = MetricGenerator(metrics=[gone, shared, custom])
    second = MetricGenerator(metrics=[live, shared])
    exporter = PrometheusExporter(metric_generators=[first, second], metric_prefix_name="tracarbon")

    await exporter._launch_all()
    assert prometheus_registry.get_sample_value("tracarbon_container_watts", {"pod_name": "gone"}) == 42.0

    first.metrics = []
    live.value = AsyncMock(return_value=0.0)
    shared.value = AsyncMock(return_value=None)
    await exporter._launch_all()

    assert prometheus_registry.get_sample_value("tracarbon_container_watts", {"pod_name": "gone"}) is None
    assert prometheus_registry.get_sample_value("tracarbon_container_watts", {"pod_name": "live"}) == 0.0
    assert prometheus_registry.get_sample_value("tracarbon_container_watts", {"pod_name": "shared"}) == 42.0
    assert prometheus_registry.get_sample_value("tracarbon_custom", {"source": "custom"}) == 7.0

    second.metrics = []
    await exporter._launch_all()
    assert prometheus_registry.get_sample_value("tracarbon_container_watts", {"pod_name": "live"}) is None
    assert prometheus_registry.get_sample_value("tracarbon_container_watts", {"pod_name": "shared"}) is None


@pytest.mark.asyncio
async def test_prometheus_keeps_pods_until_kubernetes_collection_succeeds(
    mocker: MockerFixture, prometheus_registry: CollectorRegistry
) -> None:
    old, new = [
        Pod(name=name, namespace="default", containers=[Container(name="app", cpu_usage=0.1, memory_usage=0.2)])
        for name in ("old", "new")
    ]
    pods_usage = mocker.patch.object(Kubernetes, "get_pods_usage", return_value=[old])
    mocker.patch.object(
        MacEnergyConsumption, "get_energy_usage", return_value=EnergyUsage(cpu_energy_usage=12, memory_energy_usage=4)
    )
    generator = EnergyConsumptionKubernetesGenerator(
        location=Country(name="fr", co2g_kwh=50.0),
        energy_consumption=MacEnergyConsumption(),
        kubernetes=Kubernetes.model_construct(api=mocker.Mock()),
    )
    exporter = PrometheusExporter(metric_generators=[generator])
    await exporter._launch_all()

    def interrupted_pods_usage() -> Iterator[Pod]:
        yield new
        raise RuntimeError("Kubernetes collection failed")

    pods_usage.return_value = interrupted_pods_usage()
    with pytest.raises(RuntimeError, match="Kubernetes collection failed"):
        await exporter._launch_all()
    assert {sample.labels["pod_name"] for metric in prometheus_registry.collect() for sample in metric.samples} == {
        "old",
        "new",
    }

    pods_usage.return_value = []
    await exporter._launch_all()
    assert [sample for metric in prometheus_registry.collect() for sample in metric.samples] == []
