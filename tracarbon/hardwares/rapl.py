import glob
import os
import pathlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List
from typing import Tuple

import aiofiles
from loguru import logger
from pydantic import BaseModel
from pydantic import Field
from pydantic import PrivateAttr

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.energy import EnergyCounter
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import EnergyZone
from tracarbon.hardwares.energy import Power
from tracarbon.hardwares.energy import UsageType

__all__ = [
    "RAPLResult",
    "RAPL",
]

RAPL_DOMAIN_USAGE_TYPES: Dict[str, Tuple[UsageType, ...]] = {
    "package": (UsageType.HOST,),
    "memory": (UsageType.HOST, UsageType.MEMORY),
    "cpu": (UsageType.CPU,),
    "gpu": (UsageType.GPU,),
}


_MICROSECONDS_PER_SECOND = 1_000_000
_THE_NAME_OF_A_PEAK_CONSTRAINT = "peak_power"


class RAPLResult(BaseModel):
    """
    RAPL result after reading the RAPL registry.
    """

    name: str
    energy_uj: float
    max_energy_uj: float
    capped_at: tuple[float, float] | None = None
    timestamp: datetime


class RAPL(BaseModel):
    """
    RAPL to read energy consumption with Intel hardware
    """

    path: str = "/sys/class/powercap/intel-rapl"
    rapl_separator: str = ":"
    _constraints_by_zone: Dict[str, tuple[float, float] | None] = PrivateAttr(default_factory=dict)
    rapl_results: Dict[str, RAPLResult] = Field(default_factory=dict)
    file_list: List[str] = Field(default_factory=list)

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

    async def _what_constrains(self, file_path: str) -> tuple[float, float] | None:
        """
        Get what constrains a zone, reading it the first time it is asked for.

        What a zone is constrained to is a property of the machine and does not change while it
        runs, so reading it once spares the sampling loop a walk of the constraint files it takes
        every interval.

        :param file_path: the directory of the zone
        :return: the watts and the seconds they are averaged over, or None where nothing holds it
        """
        if file_path not in self._constraints_by_zone:
            self._constraints_by_zone[file_path] = await RAPL._read_the_power_the_zone_is_capped_at(file_path=file_path)
        return self._constraints_by_zone[file_path]

    @staticmethod
    async def _read_the_power_the_zone_is_capped_at(file_path: str) -> tuple[float, float] | None:
        """
        Read the highest power a zone is constrained to, and the time that constraint averages over.

        A zone is held to several constraints at once, and powercap neither orders them nor requires
        them to be named, so the highest of them is taken. That is the one that reaches the wrap
        soonest, which is the direction it is safe to be wrong in.

        A zone nested inside another draws from it, so one publishing no constraint of its own is
        held to whatever encloses it. Only the outermost zone can be constrained by nothing.

        :param file_path: the directory of the zone
        :return: the watts and the seconds they are averaged over, or None where nothing holds it
        """
        constrained_to = await RAPL._read_the_constraints_of(file_path=file_path)
        if constrained_to:
            return max(constrained_to)
        enclosing = str(pathlib.PurePath(file_path).parent)
        if await RAPL._read_a_number_from(f"{enclosing}/energy_uj") is None:
            return None
        return await RAPL._read_the_power_the_zone_is_capped_at(file_path=enclosing)

    @staticmethod
    async def _read_the_constraints_of(file_path: str) -> list[tuple[float, float]]:
        """
        Read every constraint a zone publishes for itself.

        :param file_path: the directory of the zone
        :return: the watts and the seconds they are averaged over, for each constraint published
        """
        constrained_to = []
        for constraint in sorted(glob.glob(f"{file_path}/constraint_*_max_power_uw")):
            watts = await RAPL._read_a_number_from(constraint)
            averaged_over = await RAPL._read_the_window_a_constraint_averages_over(constraint)
            if watts is None or averaged_over is None:
                return []
            if watts > 0:
                constrained_to.append((Power.watts_from_microwatts(uw=watts), averaged_over))
        return constrained_to

    @staticmethod
    async def _read_a_number_from(path: str) -> float | None:
        """
        Read one number a zone publishes.

        :param path: the file holding it
        :return: the number, or None where the file cannot be read
        """
        try:
            async with aiofiles.open(path) as published:
                return float(await published.read())
        except (OSError, ValueError):
            return None

    @staticmethod
    async def _read_the_window_a_constraint_averages_over(constraint_path: str) -> float | None:
        """
        Read the time a constraint is an average over, which is what it bounds the power across.

        A limit over a window says nothing about a shorter stretch, where the hardware is free to
        draw more and make it back later. Only a constraint naming itself a peak bounds every
        stretch, so a window that cannot be read is unknown rather than absent, and unknown is not
        something to measure against.

        :param constraint_path: the max power file of the constraint
        :return: the seconds it averages over, zero for a peak, or None where it cannot be told
        """
        microseconds = await RAPL._read_a_number_from(constraint_path.replace("_max_power_uw", "_time_window_us"))
        if microseconds is not None:
            return microseconds / _MICROSECONDS_PER_SECOND
        named = await RAPL._read_what_a_constraint_calls_itself(constraint_path)
        return 0.0 if named == _THE_NAME_OF_A_PEAK_CONSTRAINT else None

    @staticmethod
    async def _read_what_a_constraint_calls_itself(constraint_path: str) -> str:
        """
        Read the name a constraint publishes for itself.

        :param constraint_path: the max power file of the constraint
        :return: the name, or an empty string where it publishes none
        """
        try:
            async with aiofiles.open(constraint_path.replace("_max_power_uw", "_name")) as name:
                return (await name.read()).strip()
        except OSError:
            return ""

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
                    async with aiofiles.open(f"{file_path}/max_energy_range_uj") as rapl_max_energy:
                        max_energy_uj = float(await rapl_max_energy.read())
                    capped_at = await self._what_constrains(file_path=file_path)
                    rapl_results.append(
                        RAPLResult(
                            name=name,
                            energy_uj=energy_uj,
                            max_energy_uj=max_energy_uj,
                            capped_at=capped_at,
                            timestamp=datetime.now(),
                        )
                    )
        except Exception as exception:
            logger.exception("The RAPL read encountered an issue.")
            raise HardwareRAPLException(exception) from exception
        logger.debug(f"The RAPL results: {rapl_results}.")
        return rapl_results

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
        Get the energy report based on RAPL.

        :return: the energy usage report of the RAPL measurements
        """
        rapl_results = await self.get_rapl_power_usage()
        watts_by_usage_type: Dict[UsageType, float] = dict()
        for rapl_result in rapl_results:
            previous_rapl_result = self.rapl_results.get(rapl_result.name, rapl_result)
            # Round to the nearest second to make calculation stable over small IO delays
            time_difference_seconds = round((rapl_result.timestamp - previous_rapl_result.timestamp).total_seconds())
            if time_difference_seconds <= 0:
                time_difference_seconds = 1
            energy_uj = rapl_result.energy_uj
            if previous_rapl_result.energy_uj > rapl_result.energy_uj:
                logger.debug(
                    f"Wrap-around detected in RAPL {rapl_result.name}. "
                    f"The current RAPL energy value ({rapl_result.energy_uj}) "
                    f"is lower than previous value ({previous_rapl_result.energy_uj})."
                )
                energy_uj = energy_uj + rapl_result.max_energy_uj
            watts = Power.watts_from_microjoules((energy_uj - previous_rapl_result.energy_uj) / time_difference_seconds)
            self.rapl_results[rapl_result.name] = rapl_result
            domain = self._classify_domain(rapl_result.name)
            for usage_type in RAPL_DOMAIN_USAGE_TYPES.get(domain, ()):
                watts_by_usage_type[usage_type] = watts_by_usage_type.get(usage_type, 0.0) + watts
        energy_usage_report = EnergyUsage(
            host_energy_usage=watts_by_usage_type.get(UsageType.HOST, 0.0),
            cpu_energy_usage=watts_by_usage_type.get(UsageType.CPU) or None,
            memory_energy_usage=watts_by_usage_type.get(UsageType.MEMORY) or None,
            gpu_energy_usage=watts_by_usage_type.get(UsageType.GPU) or None,
        )
        logger.debug(f"The usage energy report measured with RAPL is {energy_usage_report}.")
        return energy_usage_report

    async def get_energy_counter(self) -> EnergyCounter:
        """
        Read the cumulative energy counters RAPL exposes, one zone at a time.

        :return: the energy each zone consumed since it started counting
        """
        counter = EnergyCounter()
        for rapl_result in await self.get_rapl_power_usage():
            counter.zones[rapl_result.name] = EnergyZone(
                joules=Power.joules_from_microjoules(uj=rapl_result.energy_uj),
                wraps_at_joules=Power.joules_from_microjoules(uj=rapl_result.max_energy_uj),
                counts_at_most_watts=rapl_result.capped_at[0] if rapl_result.capped_at else None,
                averaged_over_seconds=rapl_result.capped_at[1] if rapl_result.capped_at else 0.0,
                usage_types=RAPL_DOMAIN_USAGE_TYPES.get(self._classify_domain(rapl_result.name), ()),
            )
        logger.debug(f"The RAPL energy zones read {counter.zones}.")
        return counter
