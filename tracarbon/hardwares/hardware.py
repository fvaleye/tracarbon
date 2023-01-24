import platform
from typing import Optional

import psutil
from pydantic import BaseModel

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
    def get_number_of_cores(logical: bool = True) -> int:
        """
        Get the number of CPU's cores.

        :param: logical: core as logical included
        :return: the number of CPU's cores
        """
        return psutil.cpu_count(logical=logical)

    @staticmethod
    def get_cpu_usage(interval: Optional[float] = None) -> float:
        """
        Get the CPU load percentage usage.

        :param interval: the minimal interval to wait between two consecutive measures
        :return: the CPU load in %
        """
        return psutil.cpu_percent(interval=interval)

    @staticmethod
    def get_memory_usage() -> float:
        """
        Get the local memory usage.

        :return: the memory used in percentage
        """
        return psutil.virtual_memory().used

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
