import os
import platform
import re
from datetime import datetime
from typing import Dict, List

import aiofiles
import psutil
from loguru import logger
from pydantic import BaseModel

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.gpu import GPUInfo


class RAPLResult(BaseModel):
    """
    RAPL result after reading the RAPL registry.
    """

    name: str
    energy_uj: float
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
            raise ValueError(
                f"Path f{self.path} doest not exists for reading RAPL energy measurements"
            )
        logger.debug(f"The hardware is RAPL compatible.")
        intel_rapl_regex = re.compile("intel-rapl")
        for directory_path, directory_names, filenames in os.walk(
            self.path, topdown=True
        ):
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
                async with aiofiles.open(f"{file_path}/name", "r") as rapl_name:
                    name = await rapl_name.read()
                    async with aiofiles.open(
                        f"{file_path}/energy_uj", "r"
                    ) as rapl_energy:
                        energy_uj = float(await rapl_energy.read())
                        max_energy_uj_value_reached = energy_uj < 1
                        if max_energy_uj_value_reached:
                            async with aiofiles.open(
                                f"{file_path}/max_energy_range_uj", "r"
                            ) as max_energy_rapl_file:
                                energy_uj = float(await max_energy_rapl_file.read())
                    rapl_results.append(
                        RAPLResult(
                            name=name, energy_uj=energy_uj, timestamp=datetime.now()
                        )
                    )
        except Exception as exception:
            logger.exception(f"The RAPL read encountered an issue.")
            raise HardwareRAPLException(exception)
        logger.debug(f"The RAPL results: {rapl_results}.")
        return rapl_results

    @staticmethod
    def _is_type(result: RAPLResult, domain: str = "host") -> bool:
        """
        Is the RAPL result is associated to the following domains:

        :return: True if matches, False otherwise
        """
        if domain == "host":
            return "package" in result.name or "ram" in result.name
        elif domain == "cpu":
            return "core" in result.name or "cpu" in result.name
        elif domain == "memory":
            print(result.name)
            return "ram" in result.name
        elif domain == "uncore":
            return "uncore" in result.name
        raise HardwareRAPLException(f"The domain {domain} is unknown.")

    async def get_total_uj(self, domain: str = "host") -> float:
        """
        Get the total microjule based on RAPL domains

        :param: domain: among the list host, memory, cpu, uncore
        :return: the energy in microjoules of the RAPL measurements
        """
        total_uj = 0.0
        rapl_results = await self.get_rapl_power_usage()
        for rapl_result in filter(
            lambda result: RAPL._is_type(result, domain), rapl_results
        ):
            previous_rapl_result = self.rapl_results.get(rapl_result.name, rapl_result)
            time_difference = (
                rapl_result.timestamp - previous_rapl_result.timestamp
            ).total_seconds()
            total_uj += (
                (rapl_result.energy_uj - previous_rapl_result.energy_uj)
                / time_difference
                if time_difference > 0
                else 1
            )
            self.rapl_results[rapl_result.name] = rapl_result
        logger.debug(
            f"The total energy measured with RAPL for {domain} is {total_uj}µj."
        )
        return total_uj


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
    async def get_cpu_usage(interval: float = 0.1) -> float:
        """
        Get the CPU load percentage usage.

        :param interval: the minimal interval to wait between two consecutive measures
        :return: the CPU load in %
        """
        return psutil.cpu_percent(interval=interval)

    @staticmethod
    async def get_memory_usage() -> float:
        """
        Get the local memory usage.

        :return: the memory usage in percentage
        """
        return psutil.virtual_memory()[2]

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.

        :return: the gpu power usage in W
        """
        return GPUInfo.get_gpu_power_usage()
