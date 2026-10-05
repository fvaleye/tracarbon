"""Estimated process energy from CPU time and Linux CPU package counters.

The allocation uses total CPU capacity, including idle, as in Scaphandre's
core-normalized process CPU usage and CodeCarbon's process tracking mode.
"""

import asyncio
import math
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import psutil
from pydantic import BaseModel
from pydantic import Field

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.amd_rapl import AMDRAPL
from tracarbon.hardwares.energy import Power
from tracarbon.hardwares.rapl import RAPL
from tracarbon.hardwares.rapl import RAPLResult
from tracarbon.hardwares.rapl import watts_between
from tracarbon.locations import CarbonIntensityMetadata
from tracarbon.locations import Location


class ProcessUsage(BaseModel):
    """One process identity and its estimated allocation over the latest interval."""

    pid: int
    created_at: float | None = None
    name: str | None = None
    status: str
    cpu_seconds: float | None = None
    cpu_capacity_fraction: float | None = None
    estimated_energy_wh: float | None = None
    estimated_co2g: float | None = None


class ProcessReport(BaseModel):
    """An interval, not a lifetime total or a direct process energy measurement."""

    method: Literal["cpu_time_over_total_capacity"] = "cpu_time_over_total_capacity"
    energy_domain: Literal["cpu_package"] = "cpu_package"
    interval_seconds: float | None
    total_cpu_seconds: float | None
    cpu_status: str
    collection_seconds: float
    energy_source: str | None
    energy_status: str
    energy_interval_min_seconds: float | None
    energy_interval_max_seconds: float | None
    source_energy_wh: float | None
    unattributed_energy_wh: float | None
    carbon_intensity_metadata: CarbonIntensityMetadata | None = None
    processes: list[ProcessUsage] = Field(default_factory=list)


@dataclass(frozen=True)
class _ProcessSnapshot:
    pid: int
    created_at: float
    name: str
    cpu_seconds: float


@dataclass(frozen=True)
class _CPUSnapshot:
    measured_at: float
    cpu_times: dict[str, float]
    processes: dict[int, _ProcessSnapshot]
    unavailable: dict[int, str]


def _read_cpu_snapshot(pids: tuple[int, ...] | None) -> _CPUSnapshot:
    processes: dict[int, _ProcessSnapshot] = {}
    unavailable: dict[int, str] = {}
    for pid in psutil.pids() if pids is None else pids:
        try:
            process = psutil.Process(pid)
            created_at = process.create_time()
            cpu_times = process.cpu_times()
            name = process.name()
            if not process.is_running():
                raise psutil.NoSuchProcess(pid)
            processes[pid] = _ProcessSnapshot(pid, created_at, name, cpu_times.user + cpu_times.system)
        except psutil.AccessDenied:
            unavailable[pid] = "access_denied"
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            unavailable[pid] = "exited"
    # Linux already includes guest and guest_nice in user and nice.
    system_times = {
        name: value for name, value in psutil.cpu_times()._asdict().items() if name not in ("guest", "guest_nice")
    }
    return _CPUSnapshot(time.monotonic(), system_times, processes, unavailable)


@dataclass(frozen=True)
class _PackageInterval:
    source: str | None = None
    status: str = "unavailable"
    energy_wh: float | None = None
    min_seconds: float | None = None
    max_seconds: float | None = None


class _PackageEnergyReader:
    def __init__(self) -> None:
        self.rapl = RAPL()
        self.amd_rapl = AMDRAPL()
        self._previous: dict[str, RAPLResult] = {}
        self._source: str | None = None

    async def _read_packages(self) -> tuple[str | None, dict[str, RAPLResult]]:
        if self.rapl.is_rapl_compatible():
            readings = await self.rapl.get_rapl_power_usage()
            return "intel_rapl", {
                reading.name: reading for reading in readings if self.rapl._classify_domain(reading.name) == "package"
            }
        if await self.amd_rapl.is_amd_rapl_compatible():
            amd_readings = await self.amd_rapl.get_amd_rapl_power_usage()
            return "amd_rapl", {
                reading.name: reading
                for reading in amd_readings
                if self.amd_rapl._classify_domain(reading.label) == "package"
            }
        return None, {}

    async def sample(self) -> _PackageInterval:
        try:
            source, current = await self._read_packages()
        except (HardwareRAPLException, OSError, ValueError):
            self._previous = {}
            return _PackageInterval()
        previous, previous_source = self._previous, self._source
        self._previous, self._source = current, source
        if not current:
            return _PackageInterval(source)
        if previous_source != source or previous.keys() != current.keys():
            return _PackageInterval(source, "baseline")
        return self._interval(previous, current, source)

    def _interval(
        self, previous: dict[str, RAPLResult], current: dict[str, RAPLResult], source: str | None
    ) -> _PackageInterval:
        joules = 0.0
        durations: list[float] = []
        for name, reading in current.items():
            before = previous[name]
            if reading.monotonic_time is None or before.monotonic_time is None:
                return _PackageInterval(source, "invalid_interval")
            duration = reading.monotonic_time - before.monotonic_time
            watts = watts_between(before, reading, self.rapl.max_power_watts.get(name, 0.0))
            if watts is None or not math.isfinite(watts) or watts < 0:
                return _PackageInterval(source, "invalid_interval")
            joules += watts * duration
            durations.append(duration)
        return _PackageInterval(source, "available", joules / 3600, min(durations), max(durations))


def _cpu_delta(previous: _CPUSnapshot | None, current: _CPUSnapshot) -> float | None:
    if previous is None or previous.cpu_times.keys() != current.cpu_times.keys():
        return None
    deltas = [value - previous.cpu_times[name] for name, value in current.cpu_times.items()]
    if any(not math.isfinite(delta) or delta < 0 for delta in deltas):
        return None
    total = sum(deltas)
    return total if total > 0 else None


def _process_usage(
    previous: _ProcessSnapshot | None, current: _ProcessSnapshot, total_cpu_seconds: float | None
) -> ProcessUsage:
    usage = ProcessUsage(pid=current.pid, created_at=current.created_at, name=current.name, status="baseline")
    if previous is None or previous.created_at != current.created_at:
        return usage
    cpu_seconds = current.cpu_seconds - previous.cpu_seconds
    if not math.isfinite(cpu_seconds) or cpu_seconds < 0:
        usage.status = "counter_reset"
        return usage
    usage.cpu_seconds = cpu_seconds
    usage.status = "available" if total_cpu_seconds is not None else "invalid_cpu_interval"
    if total_cpu_seconds is not None:
        usage.cpu_capacity_fraction = cpu_seconds / total_cpu_seconds
    return usage


def _allocate_energy(processes: list[ProcessUsage], energy_wh: float | None) -> tuple[float, bool]:
    fraction = sum(process.cpu_capacity_fraction or 0.0 for process in processes)
    if fraction > 1:
        for process in processes:
            process.cpu_capacity_fraction = None
        return 0.0, False
    allocated = 0.0
    for process in processes:
        if process.cpu_capacity_fraction is not None and energy_wh is not None:
            process.estimated_energy_wh = energy_wh * process.cpu_capacity_fraction
            allocated += process.estimated_energy_wh
    return allocated, True


class ProcessTracker:
    """Sample selected PIDs or all visible processes, without following descendants.

    Call ``sample`` once to establish baselines, then again after the desired
    interval. CPU package energy uses readable Linux RAPL counters. CPU activity
    remains available on other platforms; unsupported energy is ``None``.
    ``location`` enables carbon conversion using the existing location API.

    Allocation is package energy times process user+system CPU seconds divided
    by total system CPU seconds, including idle. The residual includes idle and
    unobserved work. Package energy can include non-core components; it is not a
    direct measurement of a process's CPU, GPU, or memory energy. Snapshots are
    sequential, so CPU and energy windows are approximate. Short-lived processes
    missed between samples and work before the first observation are excluded.
    """

    def __init__(self, pids: Iterable[int] | None = None, location: Location | None = None) -> None:
        self.pids = tuple(sorted(set(pids))) if pids is not None else None
        if self.pids is not None and (not self.pids or any(pid <= 0 for pid in self.pids)):
            raise ValueError("Select at least one positive PID, or use None for all processes.")
        self.location = location
        self._energy = _PackageEnergyReader()
        self._previous: _CPUSnapshot | None = None
        self._lock = asyncio.Lock()

    async def sample(self) -> ProcessReport:
        """Read one interval. First observations establish baselines and have no allocation."""
        async with self._lock:
            started_at = time.monotonic()
            try:
                energy = await self._energy.sample()
                current = await asyncio.to_thread(_read_cpu_snapshot, self.pids)
            except BaseException:
                self._previous = None
                self._energy = _PackageEnergyReader()
                raise
            previous, self._previous = self._previous, current
            report = self._report(previous, current, energy, current.measured_at - started_at)
            if self.location is not None and report.source_energy_wh is not None:
                intensity = await self.location.get_latest_co2g_kwh()
                report.carbon_intensity_metadata = self.location.carbon_intensity_metadata.model_copy()
                for process in report.processes:
                    if process.estimated_energy_wh is not None:
                        process.estimated_co2g = Power.co2g_from_watts_hour(process.estimated_energy_wh, intensity)
            return report

    @staticmethod
    def _report(
        previous: _CPUSnapshot | None, current: _CPUSnapshot, energy: _PackageInterval, collection_seconds: float
    ) -> ProcessReport:
        total_cpu_seconds = _cpu_delta(previous, current)
        old_processes = previous.processes if previous is not None else {}
        processes = [
            _process_usage(old_processes.get(pid), process, total_cpu_seconds)
            for pid, process in current.processes.items()
        ]
        unavailable = {pid: "exited" for pid in old_processes.keys() - current.processes.keys()}
        unavailable.update(current.unavailable)
        processes.extend(ProcessUsage(pid=pid, status=status) for pid, status in unavailable.items())
        allocated, consistent = _allocate_energy(processes, energy.energy_wh)
        cpu_status = "available" if total_cpu_seconds is not None else "baseline_or_invalid_interval"
        if not consistent:
            cpu_status = "inconsistent_cpu_times"
        return ProcessReport(
            interval_seconds=current.measured_at - previous.measured_at if previous is not None else None,
            total_cpu_seconds=total_cpu_seconds,
            cpu_status=cpu_status,
            collection_seconds=collection_seconds,
            energy_source=energy.source,
            energy_status=energy.status,
            energy_interval_min_seconds=energy.min_seconds,
            energy_interval_max_seconds=energy.max_seconds,
            source_energy_wh=energy.energy_wh,
            unattributed_energy_wh=max(0.0, energy.energy_wh - allocated) if energy.energy_wh is not None else None,
            processes=sorted(processes, key=lambda process: (-(process.cpu_seconds or 0.0), process.pid)),
        )
