import datetime
import pathlib

import pytest

from tracarbon.hardwares.amd_rapl import AMDRAPL
from tracarbon.hardwares.amd_rapl import AMDRAPLResult
from tracarbon.hardwares.energy import EnergyUsageUnit


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_is_amd_rapl_compatible_false_when_no_path():
    amd_rapl = AMDRAPL(hwmon_base_path="/nonexistent/path")
    assert await amd_rapl.is_amd_rapl_compatible() is False


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_is_amd_rapl_compatible_with_custom_path():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/amd-energy"
    amd_rapl = AMDRAPL(amd_energy_path=path)
    assert await amd_rapl.is_amd_rapl_compatible() is True


@pytest.mark.asyncio
async def test_get_amd_rapl_power_usage():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/amd-energy"
    amd_rapl = AMDRAPL(amd_energy_path=path)

    rapl_results = await amd_rapl.get_amd_rapl_power_usage()

    assert len(rapl_results) == 3

    # Sort by energy for consistent testing
    rapl_results.sort(key=lambda x: x.energy_uj)

    # Ecore1 - lowest energy
    assert rapl_results[0].label == "Ecore1"
    assert rapl_results[0].energy_uj == 11234567890.0
    assert "amd-" in rapl_results[0].name

    # Ecore0
    assert rapl_results[1].label == "Ecore0"
    assert rapl_results[1].energy_uj == 12345678901.0

    # Esocket0 - highest energy
    assert rapl_results[2].label == "Esocket0"
    assert rapl_results[2].energy_uj == 24346753748.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_energy_report_first_call():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/amd-energy"
    amd_rapl = AMDRAPL(amd_energy_path=path)

    energy_report = await amd_rapl.get_energy_report()

    # First call: time delta is 1 second by default
    # Energy values should be computed from the difference with themselves (0)
    assert energy_report.host_energy_usage == 0.0
    assert energy_report.cpu_energy_usage is None or energy_report.cpu_energy_usage == 0.0


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_get_energy_report_with_previous_results():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/amd-energy"
    one_minute_ago = datetime.datetime.now() - datetime.timedelta(seconds=60)

    # Pre-populate with previous results (simulating previous measurement)
    # Values are 60000 microjoules less than current (1 milliwatt for 60 seconds)
    one_milliwatt_per_minute = 60000
    rapl_results = {
        "amd-1-Esocket0": AMDRAPLResult(
            name="amd-1-Esocket0",
            label="Esocket0",
            energy_uj=24346753748 - one_milliwatt_per_minute,
            timestamp=one_minute_ago,
        ),
        "amd-2-Ecore0": AMDRAPLResult(
            name="amd-2-Ecore0",
            label="Ecore0",
            energy_uj=12345678901 - one_milliwatt_per_minute,
            timestamp=one_minute_ago,
        ),
        "amd-3-Ecore1": AMDRAPLResult(
            name="amd-3-Ecore1",
            label="Ecore1",
            energy_uj=11234567890 - one_milliwatt_per_minute,
            timestamp=one_minute_ago,
        ),
    }

    amd_rapl = AMDRAPL(amd_energy_path=path, rapl_results=rapl_results)

    energy_report = await amd_rapl.get_energy_report()
    energy_report.convert_unit(EnergyUsageUnit.MILLIWATT)

    # Socket consumed 60000 microjoules over 60 seconds = 1 milliwatt
    # Host = CPU = socket = 1 mW (package is the reference for AMD)
    expected_mw = 1.0

    assert round(energy_report.host_energy_usage, 2) == expected_mw
    assert round(energy_report.cpu_energy_usage, 2) == expected_mw
    assert energy_report.memory_energy_usage is None


@pytest.mark.asyncio
@pytest.mark.linux
@pytest.mark.darwin
async def test_wrap_around_detection():
    path = f"{pathlib.Path(__file__).parent.resolve()}/data/amd-energy"
    two_seconds_ago = datetime.datetime.now() - datetime.timedelta(seconds=2)

    # Simulate wrap-around: previous value was near max, current is small
    rapl_results = {
        "amd-1-Esocket0": AMDRAPLResult(
            name="amd-1-Esocket0",
            label="Esocket0",
            energy_uj=4294967290.0,  # Near 32-bit max
            timestamp=two_seconds_ago,
        ),
        "amd-2-Ecore0": AMDRAPLResult(
            name="amd-2-Ecore0",
            label="Ecore0",
            energy_uj=4294967290.0,
            timestamp=two_seconds_ago,
        ),
        "amd-3-Ecore1": AMDRAPLResult(
            name="amd-3-Ecore1",
            label="Ecore1",
            energy_uj=4294967290.0,
            timestamp=two_seconds_ago,
        ),
    }

    amd_rapl = AMDRAPL(amd_energy_path=path, rapl_results=rapl_results)

    # This should not raise an error due to wrap-around handling
    energy_report = await amd_rapl.get_energy_report()

    # Energy values should be positive (wrap-around handled correctly)
    assert energy_report.host_energy_usage >= 0
    assert energy_report.cpu_energy_usage is None or energy_report.cpu_energy_usage >= 0


def test_classify_domain():
    amd_rapl = AMDRAPL()

    assert amd_rapl._classify_domain("Esocket0") == "package"
    assert amd_rapl._classify_domain("Esocket1") == "package"
    assert amd_rapl._classify_domain("socket") == "package"
    assert amd_rapl._classify_domain("pkg0") == "package"

    assert amd_rapl._classify_domain("Ecore0") == "core"
    assert amd_rapl._classify_domain("Ecore15") == "core"
    assert amd_rapl._classify_domain("core") == "core"

    assert amd_rapl._classify_domain("unknown_label") == "unknown"
    assert amd_rapl._classify_domain("something_else") == "unknown"
