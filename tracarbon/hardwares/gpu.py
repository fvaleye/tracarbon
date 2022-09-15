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

    @classmethod
    def launch_shell_command(cls) -> Tuple[bytes, int]:
        """
        Launch a shell command.

        :return: result of the shell command and returncode
        """
        process = subprocess.Popen(
            "nvidia-smi --query-gpu=power.draw --format=csv,noheader",
            stdout=subprocess.PIPE,
            shell=True,
        )
        stdout, _ = process.communicate()
        return stdout, process.returncode

    @classmethod
    def get_gpu_power_usage(cls) -> float:
        """
        Get the GPU power usage in watts.

        :return: the gpu power usage in W
        """
        gpu_utilization, return_code = cls.launch_shell_command()
        if return_code == 0:
            return float(gpu_utilization.split()[0])
        raise HardwareNoGPUDetectedException(f"No Nvidia GPU detected.")
