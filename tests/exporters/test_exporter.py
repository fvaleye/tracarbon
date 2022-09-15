from tracarbon import Country, HardwareInfo
from tracarbon.exporters import Metric, StdoutExporter


def test_exporters_should_run_and_print_the_metrics(mocker, caplog):
    interval_in_seconds = 1
    mocker.patch.object(
        Country,
        "get_location",
        return_value=Country(name="fr", co2g_kwh=50.0),
    )
    memory_metric = Metric(
        name="test_metric_1",
        value=HardwareInfo.get_memory_usage,
        tags=["test_tags"],
    )
    cpu_metric = Metric(
        name="test_metric_2",
        value=HardwareInfo.get_cpu_usage,
        tags=["test_tags"],
    )

    metrics = [memory_metric, cpu_metric]
    exporter = StdoutExporter(quit=True, metrics=metrics)
    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    assert memory_metric.name in caplog.text
    assert str(memory_metric.value) in caplog.text
    assert str(memory_metric.tags) in caplog.text
    assert cpu_metric.name in caplog.text
    assert str(cpu_metric.value) in caplog.text
