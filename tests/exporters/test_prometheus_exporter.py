import sys
from functools import partial
from typing import Iterator
from unittest.mock import AsyncMock

import psutil
import pytest
from prometheus_client import CollectorRegistry
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


def test_prometheus_exporter_can_be_initialized_more_than_once(mocker):
    mocker.patch("tracarbon.exporters.prometheus_exporter.start_http_server")

    PrometheusExporter(quit=True, metric_generators=[], address="127.0.0.1", port=0)
    PrometheusExporter(quit=True, metric_generators=[], address="127.0.0.1", port=0)


@pytest.fixture
def prometheus_registry(mocker: MockerFixture) -> CollectorRegistry:
    registry = CollectorRegistry()
    mocker.patch("tracarbon.exporters.prometheus_exporter.start_http_server")
    mocker.patch("tracarbon.exporters.prometheus_exporter.Gauge", side_effect=partial(Gauge, registry=registry))
    return registry


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
