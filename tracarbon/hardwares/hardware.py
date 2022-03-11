import platform
from typing import Optional

import psutil
from pydantic import BaseModel


class HardwareInfo(BaseModel):
    """
    Hardware information.
    """

    @classmethod
    def get_platform(cls) -> str:
        """
        Get Platform name.
        :return:
        """
        return platform.system()

    @classmethod
    async def get_cpu_usage(cls, interval: Optional[int] = None) -> float:
        """
        Get the CPU percent usage.
        :return:
        """
        return psutil.cpu_percent(interval=interval)

    @classmethod
    async def get_memory_usage(cls) -> float:
        """
        Get the local memory usage.
        :return:
        """
        return psutil.virtual_memory()[2]
