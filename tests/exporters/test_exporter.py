import sys
from threading import Event
from threading import Thread
from threading import Timer
from threading import current_thread

import psutil
import pytest

from tracarbon import Country
from tracarbon import MetricGenerator
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricReport
from tracarbon.exporters import StdoutExporter
from tracarbon.exporters import Tag
from tracarbon.hardwares import EnergyUsageUnit


def test_exporter_restarts_periodic_collection_and_can_stop_from_a_callback():
    collected = Event()
    readings = []
    sampling_threads = []

    async def sample() -> float:
        readings.append(1.0)
        if len(readings) == 2:
            sampling_threads.append(current_thread())
            exporter.stop()
            collected.set()
        return 1.0

    exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=sample)])])
    for _ in range(2):
        readings.clear()
        collected.clear()
        try:
            exporter.start(interval_in_seconds=0)
            assert collected.wait(timeout=2)
        finally:
            exporter.stop()
        sampling_threads[-1].join(timeout=2)
        assert exporter.metric_report["sample"].call_count == 2


@pytest.mark.parametrize("restart", [False, True])
def test_exporter_settles_an_active_sample_before_stopping_or_restarting(mocker, restart):
    sampling = Event()
    release_sample = Event()
    stop_requested = Event()
    stopped = Event()
    readings = []

    async def sample() -> float:
        if readings:
            sampling.set()
            release_sample.wait(timeout=2)
        readings.append(1.0)
        return 1.0

    exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=sample)])])
    exporter.start(interval_in_seconds=0)
    assert sampling.wait(timeout=2)
    previous_report = exporter.metric_report
    timer = exporter._timer
    set_stop_event = exporter.event.set

    def request_stop() -> None:
        set_stop_event()
        stop_requested.set()

    mocker.patch.object(exporter.event, "set", side_effect=request_stop)

    def stop() -> None:
        if restart:
            exporter.start(interval_in_seconds=3600)
        else:
            exporter.stop()
        stopped.set()

    stopping = Thread(target=stop)
    stopping.start()
    try:
        assert stop_requested.wait(timeout=2)
        assert not stopped.wait(timeout=0.05)
    finally:
        release_sample.set()
        stopping.join(timeout=2)
        timer.join(timeout=2)
        exporter.stop()

    assert stopped.is_set()
    assert previous_report["sample"].call_count == 2
    assert exporter.metric_report["sample"].call_count == (1 if restart else 2)
    assert not timer.is_alive()


def test_exporter_rejects_restarting_from_a_collection_callback():
    async def sample() -> float:
        with pytest.raises(RuntimeError, match="collection callback"):
            exporter.start(interval_in_seconds=1)
        return 1.0

    exporter = StdoutExporter(metric_generators=[MetricGenerator(metrics=[Metric(name="sample", value=sample)])])
    try:
        exporter.start(interval_in_seconds=3600)
    finally:
        exporter.stop()

    assert exporter.metric_report["sample"].call_count == 1


def test_exporter_serializes_concurrent_starts(mocker):
    first_start_stopped = Event()
    second_start_stopped = Event()
    publish_first_start = Event()
    timers = []
    exporter = StdoutExporter(metric_generators=[])
    original_stop = StdoutExporter.stop

    def stop_before_start() -> None:
        original_stop(exporter)
        if first_start_stopped.is_set():
            second_start_stopped.set()
        else:
            first_start_stopped.set()
            publish_first_start.wait(timeout=2)

    def create_timer(*args):
        timer = Timer(*args)
        timers.append(timer)
        return timer

    mocker.patch.object(StdoutExporter, "stop", side_effect=stop_before_start)
    mocker.patch("tracarbon.exporters.exporter.Timer", side_effect=create_timer)
    first_start = Thread(target=exporter.start, args=(3600,))
    second_start = Thread(target=exporter.start, args=(3600,))
    first_start.start()
    try:
        assert first_start_stopped.wait(timeout=2)
        second_start.start()
        assert not second_start_stopped.wait(timeout=0.05)
        publish_first_start.set()
        first_start.join(timeout=2)
        second_start.join(timeout=2)
        original_stop(exporter)
        assert len(timers) == 2
        assert all(not timer.is_alive() for timer in timers)
    finally:
        publish_first_start.set()
        first_start.join(timeout=2)
        if second_start.ident is not None:
            second_start.join(timeout=2)
        for timer in timers:
            timer.cancel()
            timer.join(timeout=2)


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


def _metric(units: str = EnergyUsageUnit.WATT.value, **tags) -> Metric:
    async def a_reading() -> float:
        return 60.0

    return Metric(
        name="test_power_metric",
        value=a_reading,
        tags=[Tag(key="units", value=units)] + [Tag(key=k, value=v) for k, v in tags.items()],
    )


def test_metric_report_totals_power_as_the_energy_it_delivered():
    power_metric = _metric()
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=power_metric)

    report.accumulate(metric=power_metric, value=60.0, measured_at=0.0)

    assert report.total == 0.0
    assert report.total_unit == "watt-hours"

    report.accumulate(metric=power_metric, value=60.0, measured_at=60.0)

    assert report.total == 1.0
    assert report.average == 60.0


def test_metric_report_totals_power_reported_in_milliwatts():
    milliwatt_metric = _metric(units=EnergyUsageUnit.MILLIWATT.value)
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=milliwatt_metric)
    sixty_watts_in_milliwatts = 60000.0
    a_minute_of_sixty_watts_in_watt_hours = 1.0

    report.accumulate(metric=milliwatt_metric, value=sixty_watts_in_milliwatts, measured_at=0.0)
    report.accumulate(metric=milliwatt_metric, value=sixty_watts_in_milliwatts, measured_at=60.0)

    assert report.total == a_minute_of_sixty_watts_in_watt_hours


def test_metric_report_totals_every_series_that_shares_a_metric_name():
    first_container = _metric(container_name="first")
    second_container = _metric(container_name="second")
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=first_container)
    a_watt_hour_from_each_of_the_two_series = 2.0

    report.accumulate(metric=first_container, value=60.0, measured_at=0.0)
    report.accumulate(metric=second_container, value=60.0, measured_at=0.0)
    report.accumulate(metric=first_container, value=60.0, measured_at=60.0)
    report.accumulate(metric=second_container, value=60.0, measured_at=60.0)

    assert report.total == a_watt_hour_from_each_of_the_two_series


def test_metric_report_keeps_distinct_series_when_formatted_tags_collide():
    first_series = _metric(a="b,c:d")
    second_series = _metric(a="b", c="d")
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=first_series)

    report.accumulate(metric=first_series, value=60.0, measured_at=0.0)
    report.accumulate(metric=second_series, value=60.0, measured_at=60.0)

    assert report.total == 0.0


@pytest.mark.asyncio
async def test_exporter_totals_established_series_when_a_new_series_reports_first(mocker):
    first_container = _metric(container_name="first")
    second_container = _metric(container_name="second")
    new_container = _metric(container_name="new")
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=first_container)
    two_hours = 7200.0
    two_one_minute_windows_from_each_series = 4.0
    two_hours_of_sixty_watts_from_each_series = 240.0

    for measured_at in (0.0, 60.0, 120.0):
        report.accumulate(metric=first_container, value=60.0, measured_at=measured_at)
        report.accumulate(metric=second_container, value=60.0, measured_at=measured_at)

    exporter = StdoutExporter(
        metric_generators=[MetricGenerator(metrics=[new_container, first_container, second_container])],
        metric_report={first_container.name: report},
    )
    mocker.patch("tracarbon.exporters.exporter.time.monotonic", return_value=120.0 + two_hours)

    await exporter._launch_all()

    assert report.total == two_one_minute_windows_from_each_series + two_hours_of_sixty_watts_from_each_series


@pytest.mark.asyncio
async def test_exporter_forgets_a_series_absent_from_the_current_cycle(mocker):
    gone_container = _metric(container_name="gone")
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=gone_container)
    report.accumulate(metric=gone_container, value=60.0, measured_at=0.0)
    report.accumulate(metric=gone_container, value=60.0, measured_at=60.0)
    exporter = StdoutExporter(metric_generators=[], metric_report={gone_container.name: report})
    mocker.patch("tracarbon.exporters.exporter.time.monotonic", return_value=7200.0)
    the_one_minute_window_before_it_went_away = 1.0

    await exporter._launch_all()
    report.accumulate(metric=gone_container, value=60.0, measured_at=7200.0)

    assert report.total == the_one_minute_window_before_it_went_away


def test_metric_report_averages_every_interval():
    power_metric = _metric()
    report = MetricReport(exporter_name=StdoutExporter.get_name(), metric=power_metric)

    for measured_at in (0.0, 10.0, 30.0, 60.0):
        report.accumulate(metric=power_metric, value=60.0, measured_at=measured_at)

    assert report.average_interval_in_seconds == 20.0


@pytest.mark.asyncio
async def test_metric_report_totals_a_metric_that_is_not_power_as_itself():
    carbon_metric = _metric(units="co2g")
    exporter = StdoutExporter(metric_generators=[])

    await exporter.add_metric_to_report(metric=carbon_metric, value=1.5)
    report = await exporter.add_metric_to_report(metric=carbon_metric, value=2.5)

    assert report.total == 4.0
    assert report.total_unit == "co2g"
    assert report.average == 2.0
