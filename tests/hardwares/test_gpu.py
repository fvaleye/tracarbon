import shutil

import pytest

from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares.gpu import NvidiaGPU


def test_get_nvidia_gpu_power_usage(mocker):
    gpu_power_usage_returned = "226 W"
    gpu_usage_expected = 226
    mocker.patch.object(shutil, "which", return_value=True)
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=[gpu_power_usage_returned, 0])

    gpu_usage = NvidiaGPU.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_nvidia_gpu_power_usage_should_throw_error():
    with pytest.raises(TracarbonException) as exception:
        NvidiaGPU.get_gpu_power_usage()
    assert exception.value.args[0] == "Nvidia GPU with nvidia-smi not found in PATH."
