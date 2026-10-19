import os
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List

import psutil
from loguru import logger
from pydantic import BaseModel
from pydantic import PrivateAttr

_PSUTIL_COUNTS_REAPED_CHILDREN = not (psutil.MACOS or psutil.WINDOWS)


@dataclass(frozen=True, slots=True)
class ProcessUsage:
    """A process tree's share of total CPU capacity, including idle time."""

    pid: int
    name: str
    cpu_usage: float


@dataclass(frozen=True, slots=True)
class _ProcessTreeReading:
    total_cpu_seconds: float
    read_at: float
    cpu_seconds_by_pid: Dict[int, float]


def _cpu_seconds(cpu_times: Any) -> float:
    return cpu_times.user + cpu_times.system + cpu_times.children_user + cpu_times.children_system


def _tree_cpu_seconds_by_pid(process: psutil.Process) -> Dict[int, float]:
    root_cpu_times = os.times() if process.pid == os.getpid() else process.cpu_times()
    cpu_seconds_by_pid = {process.pid: _cpu_seconds(root_cpu_times)}
    for child in process.children(recursive=True):
        with suppress(psutil.Error):
            cpu_seconds_by_pid[child.pid] = _cpu_seconds(child.cpu_times())
    return cpu_seconds_by_pid


def _cumulative_cpu_seconds(
    cpu_seconds_by_pid: Dict[int, float], previous: _ProcessTreeReading | None, counts_reaped_children: bool
) -> float:
    if previous is None:
        return sum(cpu_seconds_by_pid.values())
    if counts_reaped_children:
        return max(sum(cpu_seconds_by_pid.values()), previous.total_cpu_seconds)
    return previous.total_cpu_seconds + sum(
        seconds - previous.cpu_seconds_by_pid.get(pid, 0.0) for pid, seconds in cpu_seconds_by_pid.items()
    )


class Processes(BaseModel):
    """Track selected process trees until their root exits, without following reused PIDs."""

    pids: List[int]
    _processes: Dict[int, tuple[psutil.Process, str]] = PrivateAttr(default_factory=dict)
    _cpu_readings: Dict[int, _ProcessTreeReading] = PrivateAttr(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        for pid in self.pids:
            try:
                process = psutil.Process(pid)
                self._processes[pid] = (process, process.name())
            except psutil.Error as error:
                logger.warning(f"Process {pid} cannot be read, so no energy is attributed to it: {error}")

    def reset(self) -> None:
        """Start new CPU measurement intervals."""
        self._cpu_readings.clear()

    def get_processes_usage(self) -> List[ProcessUsage]:
        """Return each process tree's CPU share since its previous read, or zero on its first."""
        cpu_count = psutil.cpu_count()
        processes_usage = []
        for pid, (process, name) in list(self._processes.items()):
            try:
                if not process.is_running():
                    raise psutil.NoSuchProcess(pid)
                cpu_seconds_by_pid = _tree_cpu_seconds_by_pid(process)
            except psutil.Error as error:
                logger.info(f"Process {pid} is no longer followed: {error}")
                del self._processes[pid]
                self._cpu_readings.pop(pid, None)
                continue
            read_at = time.monotonic()
            previous = self._cpu_readings.get(pid)
            cpu_seconds = _cumulative_cpu_seconds(
                cpu_seconds_by_pid=cpu_seconds_by_pid,
                previous=previous,
                counts_reaped_children=_PSUTIL_COUNTS_REAPED_CHILDREN or (pid == os.getpid() and not psutil.WINDOWS),
            )
            self._cpu_readings[pid] = _ProcessTreeReading(
                total_cpu_seconds=cpu_seconds, read_at=read_at, cpu_seconds_by_pid=cpu_seconds_by_pid
            )
            if previous is None:
                cpu_usage = 0.0
            elif cpu_count and read_at > previous.read_at:
                cpu_usage = (cpu_seconds - previous.total_cpu_seconds) / (cpu_count * (read_at - previous.read_at))
            else:
                continue
            processes_usage.append(ProcessUsage(pid=pid, name=name, cpu_usage=cpu_usage))
        return processes_usage
