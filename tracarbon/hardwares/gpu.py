import subprocess
from abc import ABC
from typing import ClassVar, Optional, Tuple

from pydantic import BaseModel

from tracarbon.exceptions import HardwareNoGPUDetectedException


class GPUInfo(ABC, BaseModel):
    """
    GPU information.
    """

    @classmethod
    def launch_shell_command(cls, shell_command: str) -> Tuple[bytes, int]:
        """
        Launch a shell command using asyncio

        :param shell_command: launch the shell command
        :return: result of the shell command and returncode
        """
        process = subprocess.Popen(shell_command, stdout=subprocess.PIPE, shell=True)
        stdout, _ = process.communicate()
        return stdout, process.returncode

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.

        :return: the gpu power usage in W
        """
        return NvidiaGPU.get_gpu_power_usage()


class NvidiaGPU(GPUInfo):
    """
    Nvidia GPU information.
    """

    shell_command: ClassVar[str] = """nvidia-smi --query-gpu=%s --format=csv,noheader"""

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.

        :return: the gpu power usage in W
        """
        gpu_utilization, return_code = cls.launch_shell_command(
            shell_command=cls.shell_command % "power.draw"
        )
        if return_code == 0:
            return float(gpu_utilization.split()[0])
        raise HardwareNoGPUDetectedException(f"No Nvidia GPU detected.")
