from tracarbon.exporters import DatadogExporter
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator


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


def test_datadog_keeps_its_keys_out_of_its_repr(mocker):
    mocker.patch("tracarbon.exporters.datadog_exporter.initialize")
    mocker.patch("tracarbon.exporters.datadog_exporter.ThreadStats")

    exporter = DatadogExporter(api_key="SECRET_API_KEY", app_key="SECRET_APP_KEY", metric_generators=[])

    assert "SECRET" not in repr(exporter)
