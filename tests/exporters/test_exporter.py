import sys
import time

import psutil
import pytest

from tracarbon import Country
from tracarbon import MetricGenerator
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricReport
from tracarbon.exporters import StdoutExporter
from tracarbon.exporters import Tag
from tracarbon.hardwares import EnergyUsageUnit


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


async def _sixty_watts() -> float:
    return 60.0


def _power_metric(**tags) -> Metric:
    return Metric(
        name="test_power_metric",
        value=_sixty_watts,
        tags=[Tag(key="units", value=EnergyUsageUnit.WATT.value)] + [Tag(key=k, value=v) for k, v in tags.items()],
    )


def test_metric_report_totals_power_as_the_energy_it_delivered():
    power_metric = _power_metric()
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=power_metric)
    a_minute_ago = time.monotonic() - 60

    report.accumulate(metric=power_metric, value=60.0, measured_at=a_minute_ago)

    assert report.total == 0.0
    assert report.total_unit == "watt-hours"

    report.accumulate(metric=power_metric, value=60.0, measured_at=time.monotonic())

    assert round(report.total, 3) == 1.0
    assert report.average == 60.0


def test_metric_report_measures_a_window_a_clock_correction_cannot_stretch():
    power_metric = _power_metric()
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=power_metric)
    a_minute_ago = time.monotonic() - 60

    report.accumulate(metric=power_metric, value=60.0, measured_at=a_minute_ago)
    report.accumulate(metric=power_metric, value=60.0, measured_at=time.monotonic())

    # The window is measured on a clock that only moves forward, so an adjustment of the wall
    # clock between the two readings cannot lengthen or shorten the energy they bracket.
    assert round(report.total, 3) == 1.0


def test_metric_report_totals_power_reported_in_milliwatts():
    milliwatt_metric = Metric(
        name="test_milliwatt_metric",
        value=_sixty_watts,
        tags=[Tag(key="units", value=EnergyUsageUnit.MILLIWATT.value)],
    )
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=milliwatt_metric)
    a_minute_ago = time.monotonic() - 60

    report.accumulate(metric=milliwatt_metric, value=60000.0, measured_at=a_minute_ago)
    report.accumulate(metric=milliwatt_metric, value=60000.0, measured_at=time.monotonic())

    # 60000 mW is 60 W, so a minute of it is one watt-hour, not a thousand.
    assert round(report.total, 3) == 1.0


def test_metric_report_totals_every_series_that_shares_a_metric_name():
    first_container = _power_metric(container_name="first")
    second_container = _power_metric(container_name="second")
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=first_container)
    a_minute_ago = time.monotonic() - 60

    report.accumulate(metric=first_container, value=60.0, measured_at=a_minute_ago)
    report.accumulate(metric=second_container, value=60.0, measured_at=a_minute_ago)
    report.accumulate(metric=first_container, value=60.0, measured_at=time.monotonic())
    report.accumulate(metric=second_container, value=60.0, measured_at=time.monotonic())

    # One watt-hour each. Integrating both against a single time shared by the name would total one.
    assert round(report.total, 3) == 2.0


def test_metric_report_totals_every_series_reporting_slower_than_the_forget_horizon():
    first_container = _power_metric(container_name="first")
    second_container = _power_metric(container_name="second")
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=first_container)
    two_hours = 7200.0
    started_at = time.monotonic() - 3 * two_hours

    for cycle in range(4):
        measured_at = started_at + cycle * two_hours
        report.accumulate(metric=first_container, value=60.0, measured_at=measured_at)
        report.accumulate(metric=second_container, value=60.0, measured_at=measured_at)

    # Three windows of two hours at sixty watts, for each of the two series. Forgetting a series
    # between two of its own readings would drop the one still waiting its turn and total half.
    assert round(report.total, 3) == 2 * 3 * 120.0


@pytest.mark.asyncio
async def test_metric_report_totals_a_metric_that_is_not_power_as_itself():
    carbon_metric = Metric(
        name="test_carbon_metric",
        value=_sixty_watts,
        tags=[Tag(key="units", value="co2g")],
    )
    exporter = StdoutExporter(metric_generators=[])

    await exporter.add_metric_to_report(metric=carbon_metric, value=1.5)
    report = await exporter.add_metric_to_report(metric=carbon_metric, value=2.5)

    assert report.total == 4.0
    assert report.total_unit == "co2g"
    assert report.average == 2.0
