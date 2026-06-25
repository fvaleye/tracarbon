import sys

import psutil

from tracarbon import Country
from tracarbon import MetricGenerator
from tracarbon.exporters import Metric
from tracarbon.exporters import PrometheusExporter
from tracarbon.exporters import Tag


def test_prometheus_exporter(mocker):
    interval_in_seconds = 1
    memory_value = 70
    mock_memory_value = ["0", "0", memory_value]
    mocker.patch.object(psutil, "virtual_memory", return_value=mock_memory_value)
    expected_metric_1 = "gauge:tracarbon_test_metric_1"

    async def get_memory_usage() -> float:
        return psutil.virtual_memory()[2]

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

    async def get_zero_value() -> float:
        return 0.0

    kubernetes_labels = {
        "pod_name": "grafana-5745b58656-8q4q8",
        "pod_namespace": "default",
        "container_name": "grafana",
        "platform": "Linux",
        "containers": "kubernetes",
        "location": "fr",
        "source": "file",
        "units": "co2mg",
    }
    kubernetes_metric = Metric(
        name="carbon_emission_kubernetes_total",
        value=get_zero_value,
        tags=[Tag(key=key, value=value) for key, value in kubernetes_labels.items()],
    )
    metric_generators = [MetricGenerator(metrics=[memory_metric, kubernetes_metric])]
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

    samples = exporter.prometheus_metrics["tracarbon_carbon_emission_kubernetes_total"].collect()[0].samples
    assert samples[0].value == 0.0
    assert samples[0].labels == kubernetes_labels
    assert exporter.metric_report["carbon_emission_kubernetes_total"].call_count == 1
