import asyncio
import platform

from tracarbon.exceptions import HardwareIOReportException
from tracarbon.hardwares._ioreport import IOReportReader
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import UsageType

__all__ = ["IOReportEnergy"]


class IOReportEnergy:
    """Report average Apple Silicon power between consecutive IOReport samples."""

    def __init__(self) -> None:
        self._reader = IOReportReader()
        self._gpu_only = int(platform.mac_ver()[0].partition(".")[0]) >= 27

    @staticmethod
    def is_available() -> bool:
        return IOReportReader.is_available()

    async def get_energy_report(self) -> EnergyUsage:
        """
        Return component watts and a host total.

        Where CPU, memory and ANE counters stall or arrive in delayed batches, only GPU watts are returned.
        """
        interval = self._reader.read_interval()
        if interval is None:
            await asyncio.sleep(0.1)
            interval = self._reader.read_interval()
        if interval is None or interval.seconds <= 0:
            raise HardwareIOReportException("IOReport returned no sampling interval.")
        if not interval.millijoules:
            raise HardwareIOReportException("IOReport returned no readable energy channel.")

        joules = {usage: energy / 1000 for usage, energy in interval.millijoules.items()}
        watts = {usage: energy / interval.seconds for usage, energy in joules.items()}
        if self._gpu_only:
            return EnergyUsage(
                host_energy_usage=None,
                gpu_energy_usage=watts.get(UsageType.GPU),
                interval_joules={UsageType.GPU: joules[UsageType.GPU]} if UsageType.GPU in joules else {},
            )
        return EnergyUsage(
            host_energy_usage=watts.get(UsageType.HOST, 0.0),
            cpu_energy_usage=watts.get(UsageType.CPU),
            memory_energy_usage=watts.get(UsageType.MEMORY),
            gpu_energy_usage=watts.get(UsageType.GPU),
            interval_joules=joules,
        )

    def close(self) -> None:
        self._reader.close()

    def __enter__(self) -> "IOReportEnergy":
        return self

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        self.close()
