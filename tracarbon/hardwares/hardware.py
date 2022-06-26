import platform

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

        :return:
        """
        return psutil.virtual_memory()[2]

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.

        :return: the gpu power usage in W
        """
        return GPUInfo.get_gpu_power_usage()
