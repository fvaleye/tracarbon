import datetime
import pathlib

import pytest

from tracarbon import RAPL
from tracarbon.hardwares import EnergyUsageUnit, RAPLResult


@pytest.mark.linux
@pytest.mark.darwin
def test_is_rapl_compatible(tmpdir):
    assert RAPL().is_rapl_compatible() is False

    path = tmpdir.mkdir("intel-rapl")

    assert RAPL(path=str(path)).is_rapl_compatible() is True


@pytest.mark.asyncio
async def test_get_rapl_power_usage():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"

    rapl_results = await RAPL(
        path=path, rapl_separator=rapl_separator_for_windows
    ).get_rapl_power_usage()

    def by_energy_uj(rapl_result: RAPLResult) -> str:
        return rapl_result.energy_uj

    rapl_results.sort(key=by_energy_uj)
    assert rapl_results[0].name == "core"
    assert rapl_results[0].energy_uj == 3.0
    assert rapl_results[1].name == "dram"
    assert rapl_results[1].energy_uj == 2433.0
    assert rapl_results[2].name == "package-1"
    assert rapl_results[2].energy_uj == 20232.0
    assert rapl_results[3].name == "dram"
    assert rapl_results[3].energy_uj == 2592370025.0
    assert rapl_results[4].name == "package-0"
    assert rapl_results[4].energy_uj == 24346753748.0
    assert rapl_results[5].name == "core"
    assert rapl_results[5].energy_uj == 43725162336.0


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
async def test_get_total_uj_one_call():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    rapl_separator_for_windows = "T"
    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    rapl_results = dict()
    rapl_results["package-0"] = RAPLResult(
        name="package", energy_uj=50000, timestamp=one_minute_ago
    )
    rapl_results["core"] = RAPLResult(
        name="core", energy_uj=40000, timestamp=one_minute_ago
    )
    rapl = RAPL(
        path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results
    )
    host_energy_usage_expected = 0.333
    cpu_energy_usage_expected = 0.167

    energy_report = await rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)
    assert round(energy_report.host_energy_usage, 3) == host_energy_usage_expected
    assert round(energy_report.cpu_energy_usage, 3) == cpu_energy_usage_expected
    assert energy_report.memory_energy_usage is None
