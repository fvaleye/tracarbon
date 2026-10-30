from typing import Any as _Any

from tracarbon import conf as _conf
from tracarbon.hardwares.amd_rapl import AMDRAPLResult
from tracarbon.hardwares.cloud_providers import AWS
from tracarbon.hardwares.cloud_providers import GCP
from tracarbon.hardwares.cloud_providers import Azure
from tracarbon.hardwares.cloud_providers import CloudProviders
from tracarbon.hardwares.energy import EnergyUsageUnit
from tracarbon.hardwares.energy import Power
from tracarbon.hardwares.energy import UsageType
from tracarbon.hardwares.ioreport import IOReportEnergy
from tracarbon.hardwares.processes import Processes
from tracarbon.hardwares.processes import ProcessUsage
from tracarbon.hardwares.rapl import RAPLResult
from tracarbon.hardwares.sensors import AMDRAPL
from tracarbon.hardwares.sensors import RAPL
from tracarbon.hardwares.sensors import AppleSiliconPowerMetrics
from tracarbon.hardwares.sensors import AWSEC2EnergyConsumption
from tracarbon.hardwares.sensors import AzureEnergyConsumption
from tracarbon.hardwares.sensors import CloudEnergyConsumption
from tracarbon.hardwares.sensors import EnergyConsumption
from tracarbon.hardwares.sensors import EnergyUsage
from tracarbon.hardwares.sensors import GCPEnergyConsumption
from tracarbon.hardwares.sensors import GPUInfo
from tracarbon.hardwares.sensors import HardwareInfo
from tracarbon.hardwares.sensors import LinuxEnergyConsumption
from tracarbon.hardwares.sensors import MacEnergyConsumption
from tracarbon.hardwares.sensors import Sensor
from tracarbon.hardwares.sensors import WindowsEnergyConsumption

__all__ = [
    "AMDRAPL",
    "AMDRAPLResult",
    "AWS",
    "AWSEC2EnergyConsumption",
    "AppleSiliconPowerMetrics",
    "Azure",
    "AzureEnergyConsumption",
    "CloudEnergyConsumption",
    "CloudProviders",
    "EnergyConsumption",
    "EnergyUsage",
    "EnergyUsageUnit",
    "GCP",
    "GCPEnergyConsumption",
    "GPUInfo",
    "HardwareInfo",
    "IOReportEnergy",
    "LinuxEnergyConsumption",
    "MacEnergyConsumption",
    "Power",
    "ProcessUsage",
    "Processes",
    "RAPL",
    "RAPLResult",
    "Sensor",
    "UsageType",
    "WindowsEnergyConsumption",
]

# Resolve optional exports on access while keeping the static exports visible to tooling.
_PUBLIC_EXPORTS = __all__
del __all__

_KUBERNETES_EXPORTS = ("Container", "Kubernetes", "Pod")


def __getattr__(name: str) -> _Any:
    if name == "KUBERNETES_INSTALLED":
        return _conf.KUBERNETES_INSTALLED
    if name == "__all__":
        exports = _PUBLIC_EXPORTS + (list(_KUBERNETES_EXPORTS) if _conf.KUBERNETES_INSTALLED else [])
        globals()[name] = exports
        return exports
    if name in _KUBERNETES_EXPORTS and _conf.KUBERNETES_INSTALLED:
        from tracarbon.hardwares import containers

        value = getattr(containers, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    exports = globals().get("__all__")
    if exports is None:
        exports = __getattr__("__all__")
    return sorted(set(globals()) | set(exports) | {"KUBERNETES_INSTALLED"})
