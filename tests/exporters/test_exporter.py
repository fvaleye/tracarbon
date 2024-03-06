import sys

import psutil
import pytest

from tracarbon import Country
from tracarbon import MetricGenerator
from tracarbon.exporters import Metric
from tracarbon.exporters import StdoutExporter
from tracarbon.exporters import Tag


def test_exporters_should_run_and_print_the_metrics(mocker, caplog):
    async def get_memory_usage() -> float:
        return psutil.virtual_memory()[2]

    interval_in_seconds = 1
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
    metric_generator = MetricGenerator(metrics=[memory_metric])

    metric_generators = [metric_generator]
    exporter = StdoutExporter(quit=True, metric_generators=metric_generators)
    exporter.start(interval_in_seconds=interval_in_seconds)
    exporter.stop()

    assert memory_metric.name in caplog.text
    assert str(memory_metric.value) in caplog.text
    assert str(memory_metric.tags) in caplog.text
    assert exporter.metric_report["test_metric_1"].exporter_name == StdoutExporter.get_name()
    assert exporter.metric_report["test_metric_1"].metric == memory_metric
    assert exporter.metric_report["test_metric_1"].total > 0
    assert exporter.metric_report["test_metric_1"].average > 0
    assert exporter.metric_report["test_metric_1"].minimum < sys.float_info.max
    assert exporter.metric_report["test_metric_1"].maximum > 0
    assert exporter.metric_report["test_metric_1"].call_count == 1
    assert exporter.metric_report["test_metric_1"].last_report_time is not None
    assert exporter.metric_report["test_metric_1"].average_interval_in_seconds is None


def test_metric_name_and_tags_format():
    async def get_memory_usage() -> float:
        return psutil.virtual_memory()[2]

    metric = Metric(
        name="test_metric_2",
        value=get_memory_usage,
        tags=[Tag(key="test", value="tags")],
    )
    expected_name = "tracarbon_test_metric_2"
    expected_name_without_prefix = "test_metric_2"
    expected_tags = ["test:tags"]

    metric_name = metric.format_name(metric_prefix_name="tracarbon", separator="_")
    metric_name_without_prefix = metric.format_name(separator="_")
    metric_tags = metric.format_tags(separator=":")

    assert metric_name == expected_name
    assert expected_name_without_prefix == metric_name_without_prefix
    assert metric_tags == expected_tags


@pytest.mark.asyncio
async def test_metric_generator_generate():
    async def get_memory_usage() -> float:
        return psutil.virtual_memory()[2]

    metric = Metric(
        name="test_metric_2",
        value=get_memory_usage,
        tags=[Tag(key="test", value="tags")],
    )
    metrics = [metric]

    metric_generated = await MetricGenerator(metrics=metrics).generate().__anext__()

    assert metric_generated.name == "test_metric_2"
