import asyncio
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
FIRST_INTERVAL_SECONDS = 0.1


class RAPLResult(BaseModel):
    """
    RAPL result after reading the RAPL registry.
    """

    name: str
    energy_uj: float
    max_energy_uj: float
    timestamp: datetime
    monotonic_time: float | None = None


def watts_between(previous: RAPLResult, current: RAPLResult, max_power_watts: float) -> float | None:
    """
    Return average watts between two energy counter readings.

    Correct a wrap using max_energy_uj. Treat a decrease as a reset when no wrap range is
    available or the corrected power exceeds the published limit.

    :param previous: the previous reading of the zone
    :param current: the current reading of the zone
    :param max_power_watts: published maximum watts, or zero for no limit
    :return: average watts, or None for a reset or a nonpositive interval
    """
    if current.monotonic_time is not None and previous.monotonic_time is not None:
        elapsed_seconds = current.monotonic_time - previous.monotonic_time
    else:
        elapsed_seconds = (current.timestamp - previous.timestamp).total_seconds()
    if elapsed_seconds <= 0:
        return None
    consumed_uj = current.energy_uj - previous.energy_uj
    if consumed_uj < 0:
        logger.debug(
            f"The RAPL counter {current.name} moved backwards from {previous.energy_uj} to {current.energy_uj}."
        )
        consumed_uj += current.max_energy_uj
        if consumed_uj < 0 or (
            max_power_watts > 0 and consumed_uj / _MICROJOULES_PER_JOULE > max_power_watts * elapsed_seconds
        ):
            logger.warning(f"The RAPL counter {current.name} restarted, so the zone is left out of this measurement.")
            return None
    return Power.watts_from_microjoules(consumed_uj / elapsed_seconds)


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
        Check if a RAPL energy counter can be read, since the kernel lets only root read them
        after CVE-2020-8694.

        :return: if a RAPL energy counter can be read
        """
        return any(os.access(counter, os.R_OK) for counter in Path(self.path).glob("*/energy_uj"))

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
        Read energy counters, ranges, and timestamps from RAPL sysfs.

        :return: a list of the RAPL results.
        """
        rapl_results = list()
        try:
            if not self.file_list:
                self.get_rapl_files_list()
            for file_path in self.file_list:
                name_prefix = Path(file_path).name.replace("intel-rapl", "")
                async with aiofiles.open(f"{file_path}/name") as rapl_name:
                    name = (await rapl_name.read()).strip()
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

    async def get_energy_report(self) -> EnergyUsage:
        """
        Return average watts by domain.

        Without a previous sample, read twice over a short interval.

        :return: a power report with None for unmeasured domains
        """
        rapl_results = await self.get_rapl_power_usage()
        if not self.rapl_results:
            self.rapl_results = {rapl_result.name: rapl_result for rapl_result in rapl_results}
            await asyncio.sleep(FIRST_INTERVAL_SECONDS)
            rapl_results = await self.get_rapl_power_usage()
        rapl_results.sort(key=lambda result: self._classify_domain(result.name) != "package")
        restarted_package_prefixes: set[str] = set()
        watts_by_domain: Dict[str, float] = {}
        for rapl_result in rapl_results:
            previous_rapl_result = self.rapl_results.get(rapl_result.name)
            self.rapl_results[rapl_result.name] = rapl_result
            domain = self._classify_domain(rapl_result.name)
            zone_prefix = rapl_result.name.partition("-")[0]
            if previous_rapl_result is None or any(
                zone_prefix.startswith(f"{package_prefix}{self.rapl_separator}")
                for package_prefix in restarted_package_prefixes
            ):
                continue
            watts = watts_between(
                previous=previous_rapl_result,
                current=rapl_result,
                max_power_watts=self.max_power_watts.get(rapl_result.name, 0.0),
            )
            if watts is None:
                if domain == "package":
                    restarted_package_prefixes.add(zone_prefix)
                continue
            watts_by_domain[domain] = watts_by_domain.get(domain, 0.0) + watts
        host_watts = [watts_by_domain[domain] for domain in ("package", "memory") if domain in watts_by_domain]
        energy_usage_report = EnergyUsage(
            host_energy_usage=sum(host_watts) if host_watts else None,
            cpu_energy_usage=watts_by_domain.get("cpu"),
            memory_energy_usage=watts_by_domain.get("memory"),
            gpu_energy_usage=watts_by_domain.get("gpu"),
        )
        logger.debug(f"The usage energy report measured with RAPL is {energy_usage_report}.")
        return energy_usage_report
