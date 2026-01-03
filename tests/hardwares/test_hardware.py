import platform
import shutil
from collections import namedtuple

import psutil

from tracarbon import HardwareInfo
from tracarbon.hardwares.gpu import NvidiaGPU


def test_get_platform_should_return_the_platform():
    platform_expected = platform.system()

    platform_returned = HardwareInfo.get_platform()

    assert platform_returned == platform_expected


def test_get_cpu_usage(mocker):
    cpu_usage_expected = 10.0
    mocker.patch.object(psutil, "cpu_percent", return_value=10.0)

    cpu_usage = HardwareInfo.get_cpu_usage()

    assert cpu_usage == cpu_usage_expected


def test_get_memory_usage(mocker):
    memory_usage_expected = 30.0
    Memory = namedtuple("Memory", "used")
    return_value = Memory(used=memory_usage_expected)
    mocker.patch.object(psutil, "virtual_memory", return_value=return_value)

    memory_usage = HardwareInfo.get_memory_usage()

    assert memory_usage == memory_usage_expected


def test_get_memory_total(mocker):
    memory_total_expected = 300000.0
    Memory = namedtuple("Memory", "total")
    return_value = Memory(total=memory_total_expected)
    mocker.patch.object(psutil, "virtual_memory", return_value=return_value)

    memory_usage = HardwareInfo.get_memory_total()

    assert memory_usage == memory_total_expected


def test_get_cpu_count(mocker):
    return_value = 2
    mocker.patch.object(psutil, "cpu_count", return_value=return_value)

    cores = HardwareInfo.get_number_of_cores()

    assert cores == return_value


def test_get_gpu_power_usage(mocker):
    gpu_power_usage_returned = b"226 W"
    gpu_usage_expected = 226
    mocker.patch.object(shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(NvidiaGPU, "launch_shell_command", return_value=(gpu_power_usage_returned, 0))
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")

    gpu_usage = HardwareInfo.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_gpu_power_usage_with_non_zero_return_code(mocker):
    from tracarbon.exceptions import HardwareNoGPUDetectedException
    from tracarbon.hardwares.gpu import GPUInfo

    mocker.patch.object(
        NvidiaGPU,
        "get_gpu_power_usage",
        side_effect=HardwareNoGPUDetectedException("No Nvidia GPU detected."),
    )
    mocker.patch("tracarbon.hardwares.gpu.platform.system", return_value="Linux")
    mocker.patch("tracarbon.hardwares.gpu.shutil.which", return_value=None)

    gpu_usage = GPUInfo.get_gpu_power_usage()
    assert gpu_usage == 0.0


def test_get_gpu_power_usage_with_no_gpu(mocker):
    mocker.patch.object(shutil, "which", return_value=None)

    gpu_usage = HardwareInfo.get_gpu_power_usage()
    assert gpu_usage == 0.0
