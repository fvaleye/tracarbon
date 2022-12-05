import os
import platform
import re
from typing import List

import aiofiles
import psutil
from aiocache import cached
from pydantic import BaseModel

from tracarbon.exceptions import HardwareRAPLException
from tracarbon.hardwares.gpu import GPUInfo


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

    @classmethod
    def is_rapl_compatible(cls, path: str = "/sys/class/powercap/intel-rapl") -> bool:
        """
        Check if the path of the hardware for reading RAPL energy measurements exists.

        :param path: the path for reading files containing RAPL energy measurements.
        :return: if the RAPL files path exists
        """
        return os.path.exists(path)

    @classmethod
    @cached()  # type: ignore
    async def get_rapl_files_list(
        cls, path: str = "/sys/class/powercap/intel-rapl", rapl_separator: str = ":"
    ) -> List[str]:
        """
        Get the list of files containing RAPL energy measurements.
        Raise error if it's the hardware is not compatible with RAPL.

        :parm rapl_separator: only used for testing purposes on finding RAPL files on the Windows file system.
        :param path: the path for reading files containing RAPL energy measurements.
        :return: the list of files path containing RAPL energy measurements.
        """
        if not cls.is_rapl_compatible(path=path):
            raise ValueError(
                f"Path f{path} doest not exists for reading RAPL energy measurements"
            )
        file_list = list()
        intel_rapl_regex = re.compile("intel-rapl")
        for file_path in os.listdir(path):
            if intel_rapl_regex.search(file_path) and rapl_separator in file_path:
                file_list.append(os.path.join(path, file_path))
        return file_list

    @classmethod
    async def get_rapl_power_usage(
        cls, path: str = "/sys/class/powercap/intel-rapl", rapl_separator: str = ":"
    ) -> float:
        """
        Read the RAPL energy measurements files on the path provided.

        If energy_uj is greater than max_energy_range_uj, the value is set to 0.
        In this case, max_energy_range_uj contanst must be returned.

        :parm path for reading files containing RAPL energy measurements.
        :parm rapl_separator only used for testing purposes on finding RAPL files on the Windows file system.
        :return: the sum of the RAPL energy measurements in microjoules
        """
        microjoules = 0.0
        try:
            for file_path in await cls.get_rapl_files_list(
                path=path, rapl_separator=rapl_separator
            ):
                async with aiofiles.open(f"{file_path}/energy_uj", "r") as rapl_file:
                    rapl_microjoules = float(await rapl_file.read())
                    max_energy_uj_value_reached = rapl_microjoules < 1
                    if max_energy_uj_value_reached:
                        async with aiofiles.open(
                            f"{file_path}/max_energy_range_uj", "r"
                        ) as max_energy_rapl_file:
                            rapl_microjoules = float(await max_energy_rapl_file.read())
                    microjoules += rapl_microjoules
        except Exception as exception:
            raise HardwareRAPLException(exception)
        return microjoules
