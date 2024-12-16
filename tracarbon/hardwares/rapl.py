import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional

import aiofiles
from loguru import logger
from pydantic import BaseModel

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.energy import EnergyUsage
from tracarbon.hardwares.energy import Power


class RAPLResult(BaseModel):
    """
    RAPL result after reading the RAPL registry.
    """

    name: str
    energy_uj: float
    max_energy_uj: float
    timestamp: datetime


class RAPL(BaseModel):
    """
    RAPL to read energy consumption with Intel hardware
    """

    path: str = "/sys/class/powercap/intel-rapl"
    rapl_separator: str = ":"
    rapl_results: Dict[str, RAPLResult] = dict()
    file_list: List[str] = list()

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
        logger.debug(f"The hardware is RAPL compatible.")
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
                async with aiofiles.open(f"{file_path}/name", "r") as rapl_name:
                    name = await rapl_name.read()
                    name = f"{name_prefix}-{name}"
                    async with aiofiles.open(f"{file_path}/energy_uj", "r") as rapl_energy:
                        energy_uj = float(await rapl_energy.read())
                    async with aiofiles.open(f"{file_path}/max_energy_range_uj", "r") as rapl_max_energy:
                        max_energy_uj = float(await rapl_max_energy.read())
                    rapl_results.append(
                        RAPLResult(
                            name=name,
                            energy_uj=energy_uj,
                            max_energy_uj=max_energy_uj,
                            timestamp=datetime.now(),
                        )
                    )
        except Exception as exception:
            logger.exception(f"The RAPL read encountered an issue.")
            raise HardwareRAPLException(exception) from exception
        logger.debug(f"The RAPL results: {rapl_results}.")
        return rapl_results

    async def get_energy_report(self) -> EnergyUsage:
        """
        Get the energy report based on RAPL.

        :return: the energy usage report of the RAPL measurements
        """
        rapl_results = await self.get_rapl_power_usage()
        host_energy_usage_watts = 0.0
        cpu_energy_usage_watts = 0.0
        memory_energy_usage_watts = 0.0
        gpu_energy_usage_watts = 0.0
        for rapl_result in rapl_results:
            previous_rapl_result = self.rapl_results.get(rapl_result.name, rapl_result)
            time_difference = (rapl_result.timestamp - previous_rapl_result.timestamp).total_seconds()
            energy_uj = rapl_result.energy_uj
            if previous_rapl_result.energy_uj > rapl_result.energy_uj:
                logger.debug(
                    f"Wrap-around detected in RAPL {rapl_result.name}. The current RAPL energy value ({rapl_result.energy_uj}) is lower than previous value ({previous_rapl_result.energy_uj})."
                )
                energy_uj = energy_uj + rapl_result.max_energy_uj
            watts = Power.watts_from_microjoules(
                ((energy_uj - previous_rapl_result.energy_uj) / time_difference if time_difference > 0 else 1)
            )
            self.rapl_results[rapl_result.name] = rapl_result
            if "package" in rapl_result.name or "ram" in rapl_result.name:
                host_energy_usage_watts += watts
            if "core" in rapl_result.name or "cpu" in rapl_result.name:
                cpu_energy_usage_watts += watts
            if "ram" in rapl_result.name:
                memory_energy_usage_watts += watts
            if "uncore" in rapl_result.name:
                gpu_energy_usage_watts += watts
        energy_usage_report = EnergyUsage(
            host_energy_usage=host_energy_usage_watts,
            cpu_energy_usage=(cpu_energy_usage_watts if cpu_energy_usage_watts > 0 else None),
            memory_energy_usage=(memory_energy_usage_watts if memory_energy_usage_watts > 0 else None),
            gpu_energy_usage=(gpu_energy_usage_watts if gpu_energy_usage_watts > 0 else None),
        )
        logger.debug(f"The usage energy report measured with RAPL is {energy_usage_report}.")
        return energy_usage_report
