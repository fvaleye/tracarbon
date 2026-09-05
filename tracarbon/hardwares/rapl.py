import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List

import aiofiles
from loguru import logger
from pydantic import BaseModel
from pydantic import Field

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import Power

__all__ = [
    "RAPLResult",
    "RAPL",
]

_MICROWATTS_PER_WATT = 1000000
_MICROJOULES_PER_JOULE = 1000000


class RAPLResult(BaseModel):
    """
    RAPL result after reading the RAPL registry.
    """

    name: str
    energy_uj: float
    max_energy_uj: float
    timestamp: datetime
    monotonic_time: float | None = None


class RAPL(BaseModel):
    """
    RAPL to read energy consumption with Intel hardware
    """

    path: str = "/sys/class/powercap/intel-rapl"
    rapl_separator: str = ":"
    rapl_results: Dict[str, RAPLResult] = Field(default_factory=dict)
    file_list: List[str] = Field(default_factory=list)
    max_power_watts: Dict[str, float] = Field(default_factory=dict)

    def is_rapl_compatible(self) -> bool:
        """
        Check if the path of the hardware for reading RAPL energy measurements exists.
        :return: if the RAPL files path exists
        """
        return os.path.exists(self.path)

    def get_rapl_files_list(self) -> None:
        """
        Get the list of files containing RAPL energy measurements.
        Raise error if it's the hardware is not compatible with RAPL.

        :return: the list of files path containing RAPL energy measurements.
        """
        if not self.is_rapl_compatible():
            raise ValueError(f"Path f{self.path} doest not exists for reading RAPL energy measurements")
        logger.debug("The hardware is RAPL compatible.")
        intel_rapl_regex = re.compile("intel-rapl")
        for directory_path, directory_names, _filenames in os.walk(self.path, topdown=True):
            for directory in directory_names:
                if not intel_rapl_regex.search(directory):
                    directory_names.remove(directory)
            current_directory = directory_path.split("/")[-1]
            if len(current_directory.split(self.rapl_separator)) >= 2:
                self.file_list.append(directory_path)
        logger.debug(f"The RAPL file list collected: {self.file_list}.")

    async def get_rapl_power_usage(self) -> List[RAPLResult]:
        """
        Read the RAPL energy measurements files on paths provided.

        If energy_uj is greater than max_energy_range_uj, the value is set to 0.
        In this case, max_energy_range_uj contanst must be returned.

        :return: a list of the RAPL results.
        """
        rapl_results = list()
        try:
            if not self.file_list:
                self.get_rapl_files_list()
            for file_path in self.file_list:
                name_prefix = Path(file_path).name.replace("intel-rapl", "")
                async with aiofiles.open(f"{file_path}/name") as rapl_name:
                    name = await rapl_name.read()
                    name = f"{name_prefix}-{name}"
                    async with aiofiles.open(f"{file_path}/energy_uj") as rapl_energy:
                        energy_uj = float(await rapl_energy.read())
                        monotonic_time = time.monotonic()
                        timestamp = datetime.now()
                    async with aiofiles.open(f"{file_path}/max_energy_range_uj") as rapl_max_energy:
                        max_energy_uj = float(await rapl_max_energy.read())
                    if name not in self.max_power_watts:
                        self.max_power_watts[name] = await self._read_max_power_watts(file_path=file_path)
                    rapl_results.append(
                        RAPLResult(
                            name=name,
                            energy_uj=energy_uj,
                            max_energy_uj=max_energy_uj,
                            timestamp=timestamp,
                            monotonic_time=monotonic_time,
                        )
                    )
        except Exception as exception:
            logger.exception("The RAPL read encountered an issue.")
            raise HardwareRAPLException(exception) from exception
        logger.debug(f"The RAPL results: {rapl_results}.")
        return rapl_results

    @staticmethod
    async def _read_max_power_watts(file_path: str) -> float:
        """
        Read the zone's highest short-term or peak power constraint.

        Long-term power can be exceeded during valid short bursts, so it cannot
        reliably distinguish a counter reset from a wrap.

        :param file_path: the directory of the zone
        :return: the published watts, or zero where the zone publishes neither
        """
        watts = 0.0
        for constraint in Path(file_path).glob("constraint_*_max_power_uw"):  # noqa: ASYNC240
            try:
                constraint_name = constraint.with_name(constraint.name.replace("_max_power_uw", "_name"))
                async with aiofiles.open(constraint_name) as published_name:
                    if (await published_name.read()).strip() not in ("short_term", "peak_power"):
                        continue
                async with aiofiles.open(constraint) as published:
                    watts = max(watts, float(await published.read()) / _MICROWATTS_PER_WATT)
            except (OSError, ValueError):
                continue
        return watts

    def _classify_domain(self, name: str) -> str:
        """
        Classify the Intel RAPL energy domain from its sysfs name.

        :param name: The energy domain name (e.g., "package-0", "dram")
        :return: Classification: "package", "memory", "cpu", "gpu", or "unknown"
        """
        name_lower = name.lower()

        if "package" in name_lower:
            return "package"
        if "dram" in name_lower or "ram" in name_lower:
            return "memory"
        if "uncore" in name_lower:
            return "gpu"
        if "core" in name_lower or "cpu" in name_lower:
            return "cpu"
        return "unknown"

    def _wrap_exceeds_max_power(self, name: str, joules: float, seconds: float) -> bool:
        """
        Check whether a wrap-adjusted reading exceeds the zone's published maximum power.

        :param name: The energy domain name (e.g., "package-0", "dram")
        :param joules: the energy the zone is taken to have consumed
        :param seconds: how long the window lasted
        :return: whether the wrap-adjusted reading exceeds the published maximum
        """
        max_power_watts = self.max_power_watts.get(name, 0.0)
        return max_power_watts > 0 and joules > max_power_watts * seconds

    async def get_energy_report(self) -> EnergyUsage:
        """
        Get the energy report based on RAPL.

        :return: the energy usage report of the RAPL measurements
        """
        rapl_results = await self.get_rapl_power_usage()
        rapl_results.sort(key=lambda result: self._classify_domain(result.name) != "package")
        restarted_package_prefixes: set[str] = set()
        host_energy_usage_watts = 0.0
        cpu_energy_usage_watts = 0.0
        memory_energy_usage_watts = 0.0
        gpu_energy_usage_watts = 0.0
        for rapl_result in rapl_results:
            previous_rapl_result = self.rapl_results.get(rapl_result.name, rapl_result)
            self.rapl_results[rapl_result.name] = rapl_result
            domain = self._classify_domain(rapl_result.name)
            zone_prefix = rapl_result.name.partition("-")[0]
            if any(
                zone_prefix.startswith(f"{package_prefix}{self.rapl_separator}")
                for package_prefix in restarted_package_prefixes
            ):
                continue
            if rapl_result.monotonic_time is not None and previous_rapl_result.monotonic_time is not None:
                elapsed_seconds = rapl_result.monotonic_time - previous_rapl_result.monotonic_time
            else:
                elapsed_seconds = (rapl_result.timestamp - previous_rapl_result.timestamp).total_seconds()
            if elapsed_seconds <= 0:
                continue
            energy_uj = rapl_result.energy_uj
            if previous_rapl_result.energy_uj > rapl_result.energy_uj:
                logger.debug(
                    f"The RAPL counter {rapl_result.name} moved backwards. "
                    f"The current RAPL energy value ({rapl_result.energy_uj}) "
                    f"is lower than previous value ({previous_rapl_result.energy_uj})."
                )
                energy_uj = energy_uj + rapl_result.max_energy_uj
                if self._wrap_exceeds_max_power(
                    name=rapl_result.name,
                    joules=(energy_uj - previous_rapl_result.energy_uj) / _MICROJOULES_PER_JOULE,
                    seconds=elapsed_seconds,
                ):
                    logger.warning(
                        f"The wrap-adjusted RAPL reading for {rapl_result.name} exceeds its published maximum "
                        f"power over this interval. Tracarbon is treating the counter as reset and leaving the "
                        f"zone out of this measurement."
                    )
                    if domain == "package":
                        restarted_package_prefixes.add(zone_prefix)
                    continue
            watts = Power.watts_from_microjoules((energy_uj - previous_rapl_result.energy_uj) / elapsed_seconds)
            if domain in ("package", "memory"):
                host_energy_usage_watts += watts
            if domain == "cpu":
                cpu_energy_usage_watts += watts
            if domain == "memory":
                memory_energy_usage_watts += watts
            if domain == "gpu":
                gpu_energy_usage_watts += watts
        energy_usage_report = EnergyUsage(
            host_energy_usage=host_energy_usage_watts,
            cpu_energy_usage=(cpu_energy_usage_watts if cpu_energy_usage_watts > 0 else None),
            memory_energy_usage=(memory_energy_usage_watts if memory_energy_usage_watts > 0 else None),
            gpu_energy_usage=(gpu_energy_usage_watts if gpu_energy_usage_watts > 0 else None),
        )
        logger.debug(f"The usage energy report measured with RAPL is {energy_usage_report}.")
        return energy_usage_report
