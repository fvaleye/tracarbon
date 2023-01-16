import psutil

from tracarbon import Country, MetricGenerator
from tracarbon.exporters import Metric, PrometheusExporter, Tag


def test_prometheus_exporter(mocker):
    interval_in_seconds = 1
    memory_value = "70"
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
    metric_generators = [MetricGenerator(metrics=[memory_metric])]
    exporter = PrometheusExporter(
        quit=True, metric_generators=metric_generators, metric_prefix_name="tracarbon"
    )
    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    assert (
        str(exporter.prometheus_metrics["tracarbon_test_metric_1"]) == expected_metric_1
    )
