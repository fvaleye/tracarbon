import psutil

from tracarbon import Country, HardwareInfo
from tracarbon.exporters import Metric, PromotheusExporter, Tag


def test_promotheus_exporter(mocker):
    interval_in_seconds = 1
    cpu_value = "5.0"
    memory_value = "70"
    mock_memory_value = ["0", "0", memory_value]
    mocker.patch.object(psutil, "cpu_percent", return_value=cpu_value)
    mocker.patch.object(psutil, "virtual_memory", return_value=mock_memory_value)
    expected_metric_1 = "gauge:tracarbon_test_metric_1"
    expected_metric_2 = "gauge:tracarbon_test_metric_2"

    mocker.patch.object(
        Country,
        "get_location",
        return_value=Country(name="fr", co2g_kwh=50.0),
    )
    memory_metric = Metric(
        name="test_metric_1",
        value=HardwareInfo.get_memory_usage,
        tags=[Tag(key="test", value="tags")],
    )
    cpu_metric = Metric(
        name="test_metric_2",
        value=HardwareInfo.get_cpu_usage,
        tags=[Tag(key="test", value="tags")],
    )
    metrics = [memory_metric, cpu_metric]
    exporter = PromotheusExporter(
        quit=True, metrics=metrics, metric_prefix_name="tracarbon"
    )
    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    assert (
        str(exporter.promotheus_metrics["tracarbon_test_metric_1"]) == expected_metric_1
    )
    assert (
        str(exporter.promotheus_metrics["tracarbon_test_metric_2"]) == expected_metric_2
    )
