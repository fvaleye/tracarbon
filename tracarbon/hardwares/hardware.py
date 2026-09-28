import platform
from typing import Any

import psutil
from pydantic import BaseModel

from tracarbon.hardwares.gpu import GPUInfo

__all__ = [
    "HardwareInfo",
]


class HardwareInfo(BaseModel):
    """
    Hardware information.
    """

    @staticmethod
    def get_platform() -> str:
        """
        Get the platform name.

        :return: the name of the platform
        """
        return platform.system()

    @staticmethod
    def get_number_of_cores(logical: bool = True) -> int:
        """
        Get the number of CPU's cores.

        :param: logical: core as logical included
        :return: the number of CPU's cores
        """
        return psutil.cpu_count(logical=logical)

    @staticmethod
    def get_cpu_usage(interval: float | None = None) -> float:
        """
        Get the CPU load percentage usage.

        :param interval: the minimal interval to wait between two consecutive measures
        :return: the CPU load in %
        """
        return psutil.cpu_percent(interval=interval)

    @staticmethod
    def get_cpu_usage_since(since: Any) -> tuple[float, Any]:
        """
        Get the CPU load percentage usage since the CPU times of the previous reading.

        psutil.cpu_percent keeps its own previous reading per thread instead, so two readers on one
        thread measure each other's windows and a reader on a new thread reads no load at all.

        :param since: the CPU times returned by the previous reading, or None to measure since boot
        :return: the CPU load in % and the CPU times to pass to the next reading
        """
        cpu_times = psutil.cpu_times()
        window = cpu_times
        if since is not None:
            window = type(cpu_times)(*(max(0.0, now - before) for now, before in zip(cpu_times, since, strict=True)))
        # Counted as psutil's _cpu_tot_time and _cpu_busy_time do: Linux already counts guest time
        # in user time, and iowait is idle time.
        total = sum(window) - getattr(window, "guest", 0.0) - getattr(window, "guest_nice", 0.0)
        busy = total - window.idle - getattr(window, "iowait", 0.0)
        return (100.0 * busy / total if total > 0 else 0.0), cpu_times

    @staticmethod
    def get_memory_usage() -> float:
        """
        Get the local memory usage.

        :return: the memory used in percentage
        """
        return psutil.virtual_memory().percent

    @staticmethod
    def get_memory_total() -> float:
        """
        Get the total physical memory available.

        :return: the total physical memory available
        """
        return psutil.virtual_memory().total

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.

        :return: the gpu power usage in W
        """
        return GPUInfo.get_gpu_power_usage()
