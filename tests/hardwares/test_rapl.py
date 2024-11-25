import datetime
import pathlib

import pytest

from tracarbon import RAPL
from tracarbon.hardwares import EnergyUsageUnit
from tracarbon.hardwares import RAPLResult


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

    rapl_results = await RAPL(path=path, rapl_separator=rapl_separator_for_windows).get_rapl_power_usage()

    def by_energy_uj(rapl_result: RAPLResult) -> str:
        return rapl_result.energy_uj

    rapl_results.sort(key=by_energy_uj)
    assert rapl_results[0].name == "T1T0-core"
    assert rapl_results[0].energy_uj == 3.0
    assert rapl_results[1].name == "T1T1-dram"
    assert rapl_results[1].energy_uj == 2433.0
    assert rapl_results[2].name == "T1-package-1"
    assert rapl_results[2].energy_uj == 20232.0
    assert rapl_results[3].name == "T0T1-dram"
    assert rapl_results[3].energy_uj == 2592370025.0
    assert rapl_results[4].name == "T0-package-0"
    assert rapl_results[4].energy_uj == 24346753748.0
    assert rapl_results[5].name == "T0T0-core"
    assert rapl_results[5].energy_uj == 43725162336.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_rapl_power_wrap_around_when_0():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    two_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=2)
    rapl_separator_for_windows = "T"
    rapl_results = dict()
    rapl_results["T0-package-0"] = RAPLResult(
        name="T0-package-0", energy_uj=2, max_energy_uj=70000, timestamp=two_seconds_ago
    )
    rapl_results["T0T0-core"] = RAPLResult(
        name="T0T0-core", energy_uj=1, max_energy_uj=70000, timestamp=two_seconds_ago
    )
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)
    host_energy_usage_expected = 35
    cpu_energy_usage_expected = 35

    energy_report = await rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)
    assert round(energy_report.host_energy_usage, 0) == host_energy_usage_expected
    assert round(energy_report.cpu_energy_usage, 0) == cpu_energy_usage_expected
    assert energy_report.memory_energy_usage is None


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_total_uj_one_call():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl2"
    rapl_separator_for_windows = "T"
    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    rapl_results = dict()
    rapl_results["T0-package-0"] = RAPLResult(
        name="T0-package-0", energy_uj=50000, max_energy_uj=70000, timestamp=one_minute_ago
    )
    rapl_results["T0T0-core"] = RAPLResult(
        name="T0T0-core", energy_uj=40000, max_energy_uj=70000, timestamp=one_minute_ago
    )
    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)
    host_energy_usage_expected = 0.33
    cpu_energy_usage_expected = 0.5

    energy_report = await rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)
    assert round(energy_report.host_energy_usage, 2) == host_energy_usage_expected
    assert round(energy_report.cpu_energy_usage, 2) == cpu_energy_usage_expected
    assert energy_report.memory_energy_usage is None


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_results_with_two_packages_are_correctly_computed():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/intel-rapl"
    rapl_separator_for_windows = "T"

    one_milliwatt = 60000

    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)
    rapl_results = dict()
    rapl_results["T0-package-0"] = RAPLResult(
        name="T0-package-0", energy_uj=24346753748 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T0T0-core"] = RAPLResult(
        name="T0T0-core", energy_uj=43725162336 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T0T1-dram"] = RAPLResult(
        name="T0T1-dram", energy_uj=2592370025 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )

    rapl_results["T1-package-1"] = RAPLResult(
        name="T1-package-1", energy_uj=20232 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T1T0-core"] = RAPLResult(
        name="T1T0-core", energy_uj=65532610987 - one_milliwatt + 3, max_energy_uj=65532610987, timestamp=one_minute_ago
    )
    rapl_results["T1T1-dram"] = RAPLResult(
        name="T1T1-dram", energy_uj=2433 - one_milliwatt, max_energy_uj=65532610987, timestamp=one_minute_ago
    )

    rapl = RAPL(path=path, rapl_separator=rapl_separator_for_windows, rapl_results=rapl_results)

    host_energy_usage_expected = 4
    cpu_energy_usage_expected = 2
    memory_energy_usage_expected = 2

    energy_report = await rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)
    assert round(energy_report.host_energy_usage, 2) == host_energy_usage_expected
    assert round(energy_report.cpu_energy_usage, 2) == cpu_energy_usage_expected
    assert round(energy_report.memory_energy_usage, 2) == memory_energy_usage_expected
    assert energy_report.gpu_energy_usage is None
