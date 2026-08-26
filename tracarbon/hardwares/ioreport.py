import asyncio

from tracarbon.exceptions import HardwareIOReportException
from tracarbon.hardwares._ioreport import IOReportReader
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import UsageType

__all__ = ["IOReportEnergy"]


class IOReportEnergy:
    """Report average Apple Silicon power between consecutive IOReport samples."""

    def __init__(self) -> None:
        self._reader = IOReportReader()

    @staticmethod
    def is_available() -> bool:
        return IOReportReader.is_available()

    async def get_energy_report(self) -> EnergyUsage:
        """Return watts per component, including ANE energy in the host total."""
        interval = self._reader.read_interval()
        if interval is None:
            await asyncio.sleep(0.1)
            interval = self._reader.read_interval()
        if interval is None or interval.seconds <= 0:
            raise HardwareIOReportException("IOReport returned no sampling interval.")
        if not interval.millijoules:
            raise HardwareIOReportException("IOReport returned no readable energy channel.")

        watts = {usage: energy / 1000 / interval.seconds for usage, energy in interval.millijoules.items()}
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
