import asyncio
import platform

from loguru import logger

from tracarbon.exceptions import HardwareIOReportException
from tracarbon.hardwares._ioreport import IOReportReader
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import UsageType

__all__ = ["IOReportEnergy"]


class IOReportEnergy:
    """Report average Apple Silicon power between consecutive IOReport samples."""

    def __init__(self) -> None:
        self._reader = IOReportReader()
        release_major = platform.mac_ver()[0].partition(".")[0]
        self._has_batched_counters = release_major.isdecimal() and int(release_major) >= 27
        if self._has_batched_counters:
            logger.warning(
                "IOReport CPU, memory and ANE readings are disabled on macOS 27 and later "
                "because their counters can arrive in delayed batches. "
                "Only GPU power is available from IOReport."
            )

    @staticmethod
    def is_available() -> bool:
        return IOReportReader.is_available()

    async def get_energy_report(self) -> EnergyUsage:
        """Return watts per component, leaving batched counters and their total unknown."""
        interval = self._reader.read_interval()
        if interval is None:
            await asyncio.sleep(0.1)
            interval = self._reader.read_interval()
        if interval is None or interval.seconds <= 0:
            raise HardwareIOReportException("IOReport returned no sampling interval.")
        if not interval.millijoules:
            raise HardwareIOReportException("IOReport returned no readable energy channel.")

        watts = {usage: energy / 1000 / interval.seconds for usage, energy in interval.millijoules.items()}
        if self._has_batched_counters:
            # Delayed batches cannot be divided by this sampling interval, even when nonzero.
            return EnergyUsage(host_energy_usage=None, gpu_energy_usage=watts.get(UsageType.GPU))
        return EnergyUsage(
            host_energy_usage=watts.get(UsageType.HOST, 0.0),
            cpu_energy_usage=watts.get(UsageType.CPU),
            memory_energy_usage=watts.get(UsageType.MEMORY),
            gpu_energy_usage=watts.get(UsageType.GPU),
        )

    def close(self) -> None:
        self._reader.close()

    def __enter__(self) -> "IOReportEnergy":
        return self

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        self.close()
