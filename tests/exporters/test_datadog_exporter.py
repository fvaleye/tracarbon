from tracarbon.exporters import DatadogExporter
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator


def test_datadog_flushes_at_the_configured_interval(mocker):
    mocker.patch("tracarbon.exporters.datadog_exporter.initialize")

    exporter = DatadogExporter(api_key="test", app_key="test", metric_generators=[], datadog_flush_interval=1)
    try:
        assert exporter.stats.flush_interval == 1
    finally:
        exporter.stats.stop()


async def test_datadog_preserves_zero_and_skips_missing_values(mocker):
    mocker.patch("tracarbon.exporters.datadog_exporter.initialize")
    stats = mocker.patch("tracarbon.exporters.datadog_exporter.ThreadStats").return_value

    async def zero() -> float:
        return 0.0

    async def missing() -> None:
        return None

    exporter = DatadogExporter(api_key="test", app_key="test", metric_generators=[])
    generator = MetricGenerator(metrics=[Metric(name="zero", value=zero), Metric(name="missing", value=missing)])

    await exporter.launch(generator)

    stats.gauge.assert_called_once_with("zero", 0.0, tags=[])
    assert set(exporter.metric_report) == {"zero"}
    assert exporter.metric_report["zero"].total == 0.0


def test_datadog_repr_hides_api_keys(mocker):
    mocker.patch("tracarbon.exporters.datadog_exporter.initialize")
    mocker.patch("tracarbon.exporters.datadog_exporter.ThreadStats")

    exporter = DatadogExporter(api_key="SECRET_API_KEY", app_key="SECRET_APP_KEY", metric_generators=[])

    assert "SECRET" not in repr(exporter)
