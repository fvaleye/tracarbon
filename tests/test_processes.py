import asyncio
import json
import os
from datetime import datetime
from unittest.mock import Mock

import psutil
import pytest
from typer.testing import CliRunner

from tracarbon import Country
from tracarbon import ProcessTracker
from tracarbon.cli import app
from tracarbon.hardwares.amd_rapl import AMDRAPLResult
from tracarbon.hardwares.rapl import RAPLResult


@pytest.fixture
def cpu_readings(mocker):
    process = Mock()
    process.create_time.return_value = 123.0
    process.name.return_value = "worker"
    process.cpu_times.side_effect = [
        Mock(user=value, system=0.0, children_user=1000.0, children_system=1000.0) for value in (1.0, 2.0, 3.0)
    ]
    process.is_running.return_value = True
    mocker.patch("tracarbon.processes.psutil.Process", return_value=process)
    mocker.patch("tracarbon.processes.psutil.pids", return_value=[10])
    mocker.patch(
        "tracarbon.processes.psutil.cpu_times",
        side_effect=[
            Mock(_asdict=lambda: {"user": 20.0, "system": 10.0, "idle": 70.0, "guest": 10.0}),
            Mock(_asdict=lambda: {"user": 22.0, "system": 10.0, "idle": 72.0, "guest": 11.0}),
            Mock(_asdict=lambda: {"user": 24.0, "system": 10.0, "idle": 74.0, "guest": 12.0}),
        ],
    )
    return process


@pytest.fixture
def package_readings(mocker):
    mocker.patch("tracarbon.processes.RAPL.is_rapl_compatible", return_value=True)
    readings = [
        [
            RAPLResult(
                name=":0-package-0",
                energy_uj=value,
                max_energy_uj=100_000_000,
                timestamp=datetime.now(),
                monotonic_time=seconds,
            ),
            RAPLResult(
                name=":0:0-core",
                energy_uj=value / 2,
                max_energy_uj=100_000_000,
                timestamp=datetime.now(),
                monotonic_time=seconds,
            ),
            RAPLResult(
                name=":0:1-dram",
                energy_uj=value / 4,
                max_energy_uj=100_000_000,
                timestamp=datetime.now(),
                monotonic_time=seconds,
            ),
        ]
        for value, seconds in [(0, 10.0), (40_000_000, 11.0), (80_000_000, 12.0)]
    ]
    mocker.patch("tracarbon.processes.RAPL.get_rapl_power_usage", side_effect=readings)
    return readings


async def test_cpu_package_energy_is_split_by_total_cpu_capacity(cpu_readings, package_readings):
    tracker = ProcessTracker(location=Country(name="test", co2g_kwh=360.0))

    baseline = await tracker.sample()
    report = await tracker.sample()

    assert baseline.source_energy_wh is None
    assert baseline.processes[0].estimated_energy_wh is None
    assert report.energy_domain == "cpu_package"
    assert report.total_cpu_seconds == 4.0
    assert report.source_energy_wh == pytest.approx(40 / 3600)
    assert report.processes[0].cpu_capacity_fraction == 0.25
    assert report.processes[0].estimated_energy_wh == pytest.approx(10 / 3600)
    assert report.processes[0].estimated_co2g == pytest.approx(0.001)
    assert report.unattributed_energy_wh == pytest.approx(30 / 3600)
    assert report.energy_interval_min_seconds == 1.0
    assert report.energy_interval_max_seconds == 1.0


async def test_multiple_processes_share_one_pool_without_redistributing_idle_energy(
    mocker, cpu_readings, package_readings
):
    other = Mock()
    other.create_time.return_value = 124.0
    other.name.return_value = "other"
    other.cpu_times.side_effect = [Mock(user=1.0, system=0.0), Mock(user=1.5, system=0.0)]
    other.is_running.return_value = True
    mocker.patch("tracarbon.processes.psutil.Process", side_effect={10: cpu_readings, 20: other}.__getitem__)
    tracker = ProcessTracker(pids=[10, 20, 10])

    await tracker.sample()
    report = await tracker.sample()

    assert [process.cpu_capacity_fraction for process in report.processes] == [0.25, 0.125]
    assert sum(process.estimated_energy_wh for process in report.processes) == pytest.approx(15 / 3600)
    assert report.unattributed_energy_wh == pytest.approx(25 / 3600)


async def test_reused_pid_starts_a_new_baseline(cpu_readings, package_readings):
    cpu_readings.create_time.side_effect = [123.0, 124.0, 124.0]
    tracker = ProcessTracker()

    await tracker.sample()
    reused = await tracker.sample()
    next_interval = await tracker.sample()

    assert reused.processes[0].created_at == 124.0
    assert reused.processes[0].status == "baseline"
    assert reused.processes[0].cpu_seconds is None
    assert reused.processes[0].estimated_energy_wh is None
    assert next_interval.processes[0].cpu_seconds == 1.0


@pytest.mark.parametrize(
    "error,status", [(psutil.AccessDenied(10), "access_denied"), (psutil.NoSuchProcess(10), "exited")]
)
async def test_unreadable_process_is_unknown_and_recovery_starts_a_baseline(
    cpu_readings, package_readings, error, status
):
    cpu_readings.cpu_times.side_effect = [Mock(user=1.0, system=0.0), error, Mock(user=9.0, system=0.0)]
    tracker = ProcessTracker()

    await tracker.sample()
    missing = await tracker.sample()
    recovered = await tracker.sample()

    assert missing.processes[0].status == status
    assert missing.processes[0].estimated_energy_wh is None
    assert recovered.processes[0].status == "baseline"
    assert recovered.processes[0].estimated_energy_wh is None


async def test_exited_process_is_reported_once_and_forgotten(mocker, cpu_readings, package_readings):
    mocker.patch("tracarbon.processes.psutil.pids", side_effect=[[10], [], []])
    tracker = ProcessTracker()

    await tracker.sample()
    missing = await tracker.sample()
    later = await tracker.sample()

    assert missing.processes[0].pid == 10
    assert missing.processes[0].status == "exited"
    assert missing.processes[0].cpu_seconds is None
    assert later.processes == []


@pytest.mark.parametrize("cpu_seconds", [0.0, 10.0, float("nan")])
async def test_invalid_process_delta_never_allocates_more_than_the_pool(cpu_readings, package_readings, cpu_seconds):
    cpu_readings.cpu_times.side_effect = [Mock(user=1.0, system=0.0), Mock(user=cpu_seconds, system=0.0)]
    tracker = ProcessTracker()

    await tracker.sample()
    report = await tracker.sample()

    assert report.processes[0].estimated_energy_wh is None
    assert report.unattributed_energy_wh == report.source_energy_wh


@pytest.mark.parametrize("power_available", [False, True])
async def test_zero_cpu_usage_is_distinct_from_unknown_energy(mocker, cpu_readings, package_readings, power_available):
    cpu_readings.cpu_times.side_effect = [Mock(user=1.0, system=0.0), Mock(user=1.0, system=0.0)]
    if not power_available:
        mocker.patch("tracarbon.processes.RAPL.is_rapl_compatible", return_value=False)
        mocker.patch("tracarbon.processes.AMDRAPL.is_amd_rapl_compatible", return_value=False)
    tracker = ProcessTracker()

    await tracker.sample()
    report = await tracker.sample()

    assert report.processes[0].cpu_seconds == 0.0
    assert report.processes[0].cpu_capacity_fraction == 0.0
    assert report.processes[0].estimated_energy_wh == (0.0 if power_available else None)


async def test_zero_package_energy_is_preserved(cpu_readings, package_readings):
    package_readings[1][0].energy_uj = 0
    tracker = ProcessTracker()

    await tracker.sample()
    report = await tracker.sample()

    assert report.source_energy_wh == 0.0
    assert report.processes[0].estimated_energy_wh == 0.0
    assert report.unattributed_energy_wh == 0.0


@pytest.mark.parametrize("total", [100.0, 99.0, float("nan")])
async def test_system_counter_stall_or_reset_keeps_all_energy_unattributed(
    mocker, cpu_readings, package_readings, total
):
    mocker.patch(
        "tracarbon.processes.psutil.cpu_times",
        side_effect=[Mock(_asdict=lambda: {"user": 100.0}), Mock(_asdict=lambda: {"user": total})],
    )
    tracker = ProcessTracker()

    await tracker.sample()
    report = await tracker.sample()

    assert report.total_cpu_seconds is None
    assert report.processes[0].cpu_seconds == 1.0
    assert report.processes[0].estimated_energy_wh is None
    assert report.unattributed_energy_wh == report.source_energy_wh


async def test_amd_allocates_package_energy_without_adding_overlapping_core_energy(
    mocker, cpu_readings, package_readings
):
    mocker.patch("tracarbon.processes.RAPL.is_rapl_compatible", return_value=False)
    mocker.patch("tracarbon.processes.AMDRAPL.is_amd_rapl_compatible", return_value=True)
    mocker.patch(
        "tracarbon.processes.AMDRAPL.get_amd_rapl_power_usage",
        side_effect=[
            [
                AMDRAPLResult(**reading.model_dump(), label="Esocket0" if index == 0 else "Ecore0")
                for index, reading in enumerate(interval)
            ]
            for interval in package_readings
        ],
    )
    tracker = ProcessTracker()

    await tracker.sample()
    report = await tracker.sample()

    assert report.energy_source == "amd_rapl"
    assert report.source_energy_wh == pytest.approx(40 / 3600)


async def test_package_counter_wrap_reuses_existing_rapl_accounting(cpu_readings, package_readings):
    package_readings[0][0].energy_uj = 90_000_000
    package_readings[1][0].energy_uj = 10_000_000
    tracker = ProcessTracker()

    await tracker.sample()
    report = await tracker.sample()

    assert report.source_energy_wh == pytest.approx(20 / 3600)


async def test_reset_in_one_package_invalidates_the_entire_energy_pool(cpu_readings, package_readings):
    for index, interval in enumerate(package_readings):
        interval.append(
            interval[0].model_copy(update={"name": ":1-package-1", "energy_uj": 30 - index, "max_energy_uj": 0.0})
        )
    tracker = ProcessTracker()

    await tracker.sample()
    report = await tracker.sample()

    assert report.energy_status == "invalid_interval"
    assert report.source_energy_wh is None
    assert report.processes[0].estimated_energy_wh is None


async def test_package_disappearance_starts_a_new_baseline(cpu_readings, package_readings):
    package_readings[0].append(package_readings[0][0].model_copy(update={"name": ":1-package-1"}))
    tracker = ProcessTracker()

    await tracker.sample()
    changed = await tracker.sample()
    recovered = await tracker.sample()

    assert changed.source_energy_wh is None
    assert recovered.source_energy_wh == pytest.approx(40 / 3600)


@pytest.mark.parametrize("error", [RuntimeError("CPU sample failed"), asyncio.CancelledError()])
async def test_failed_cpu_read_discards_both_measurement_baselines(mocker, cpu_readings, package_readings, error):
    mocker.patch(
        "tracarbon.processes.psutil.cpu_times",
        side_effect=[
            Mock(_asdict=lambda: {"user": 100.0}),
            error,
            Mock(_asdict=lambda: {"user": 108.0}),
        ],
    )
    tracker = ProcessTracker()
    await tracker.sample()

    with pytest.raises(type(error)):
        await tracker.sample()
    report = await tracker.sample()

    assert report.source_energy_wh is None
    assert report.processes[0].cpu_seconds is None


def test_process_command_emits_bounded_json_lines(mocker):
    mocker.patch("tracarbon.processes.RAPL.is_rapl_compatible", return_value=False)
    mocker.patch("tracarbon.processes.AMDRAPL.is_amd_rapl_compatible", return_value=False)

    result = CliRunner().invoke(app, ["processes", "--pid", str(os.getpid()), "--interval", "0.01", "--count", "2"])

    assert result.exit_code == 0, result.exception
    reports = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(reports) == 2
    assert all(report["processes"][0]["pid"] == os.getpid() for report in reports)
    assert all(report["source_energy_wh"] is None for report in reports)


@pytest.mark.parametrize("arguments", [["--pid", "0"], ["--count", "-1"], ["--interval", "0"]])
def test_process_command_rejects_invalid_sampling_options(arguments):
    result = CliRunner().invoke(app, ["processes", *arguments])

    assert result.exit_code == 2


@pytest.mark.parametrize("pids", [[], [0], [-1]])
def test_tracker_rejects_empty_or_invalid_process_selection(pids):
    with pytest.raises(ValueError, match="positive PID"):
        ProcessTracker(pids=pids)
