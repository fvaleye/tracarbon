import pathlib
import platform
from datetime import datetime, timedelta

import psutil
import pytest

from tracarbon import RAPL, HardwareInfo
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares import RAPLResult
from tracarbon.hardwares.gpu import NvidiaGPU


def test_get_platform_should_return_the_platform():
    platform_expected = platform.system()

    platform_returned = HardwareInfo.get_platform()

    assert platform_returned == platform_expected


@pytest.mark.asyncio
async def test_get_cpu_usage(mocker):
    cpu_usage_expected = 10.0
    mocker.patch.object(psutil, "cpu_percent", return_value=10.0)

    cpu_usage = await HardwareInfo.get_cpu_usage()

    assert cpu_usage == cpu_usage_expected


@pytest.mark.asyncio
async def test_get_memory_usage(mocker):
    memory_usage_expected = 30.0
    return_value = [0, 0, memory_usage_expected]
    mocker.patch.object(psutil, "virtual_memory", return_value=return_value)

    memory_usage = await HardwareInfo.get_memory_usage()

    assert memory_usage == memory_usage_expected


def test_get_gpu_power_usage(mocker):
    gpu_power_usage_returned = "226 W"
    gpu_usage_expected = 226
    mocker.patch.object(
        NvidiaGPU, "launch_shell_command", return_value=[gpu_power_usage_returned, 0]
    )

    gpu_usage = HardwareInfo.get_gpu_power_usage()

    assert gpu_usage == gpu_usage_expected


def test_get_gpu_power_usage_with_no_0(mocker):
    gpu_power_usage_returned = "0 W"
    mocker.patch.object(
        NvidiaGPU, "launch_shell_command", return_value=[gpu_power_usage_returned, -1]
    )

    with pytest.raises(TracarbonException) as exception:
        HardwareInfo.get_gpu_power_usage()
    assert exception.value.args[0] == "No Nvidia GPU detected."


def test_get_gpu_power_usage_with_no_gpu():
    with pytest.raises(TracarbonException) as exception:
        HardwareInfo.get_gpu_power_usage()
    assert exception.value.args[0] == "No Nvidia GPU detected."


@pytest.mark.linux
@pytest.mark.darwin
def test_is_rapl_compatible(tmpdir):
    assert RAPL().is_rapl_compatible() is False

    path = tmpdir.mkdir("intel-rapl")

    assert RAPL(path=str(path)).is_rapl_compatible() is True


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_rapl_power_usage():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"

    rapl_results = await RAPL(
        path=path, rapl_separator=rapl_separator_for_windows
    ).get_rapl_power_usage()

    def by_name(rapl_result: RAPLResult) -> str:
        return (rapl_result.name,)

    rapl_results.sort(key=by_name)
    assert rapl_results[0].name == "core"
    assert rapl_results[0].energy_uj == 3.0
    assert rapl_results[1].name == "core"
    assert rapl_results[1].energy_uj == 43725162336.0
    assert rapl_results[2].name == "dram"
    assert rapl_results[2].energy_uj == 2433.0
    assert rapl_results[3].name == "dram"
    assert rapl_results[3].energy_uj == 2592370025.0
    assert rapl_results[4].name == "package-0"
    assert rapl_results[4].energy_uj == 24346753748.0
    assert rapl_results[5].name == "package-1"
    assert rapl_results[5].energy_uj == 20232.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_rapl_power_usage_max_when_0():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    rapl_separator_for_windows = "T"

    rapl_results = await RAPL(
        path=path, rapl_separator=rapl_separator_for_windows
    ).get_rapl_power_usage()
    assert rapl_results[0].name == "package-0"
    assert rapl_results[0].energy_uj == 70000.0
    assert rapl_results[0].timestamp is not None
    assert rapl_results[1].name == "core"
    assert rapl_results[1].energy_uj == 50000.0
    assert rapl_results[1].timestamp is not None


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
@pytest.mark.parametrize(
    "domain,uj_expected", [("host", 250.0), ("memory", 0.0), ("cpu", 167.0)]
)
async def test_get_total_uj_one_call(domain, uj_expected):
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    rapl_separator_for_windows = "T"
    one_minute_ago = datetime.now() - timedelta(seconds=60)
    rapl_results = dict()
    rapl_results["package-0"] = RAPLResult(
        name="package", energy_uj=55000, timestamp=one_minute_ago
    )
    rapl_results["core"] = RAPLResult(
        name="core", energy_uj=40000, timestamp=one_minute_ago
    )
    rapl = RAPL(
        path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results
    )

    uj = await rapl.get_total_uj(domain=domain)
    assert round(uj, 0) == uj_expected
