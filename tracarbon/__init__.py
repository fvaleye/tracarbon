from typing import Any as _Any

from tracarbon import conf as _conf
from tracarbon.builder import Tracarbon
from tracarbon.builder import TracarbonBuilder
from tracarbon.builder import TracarbonReport
from tracarbon.conf import DATADOG_INSTALLED
from tracarbon.conf import PROMETHEUS_INSTALLED
from tracarbon.conf import TracarbonConfiguration
from tracarbon.conf import check_optional_dependency
from tracarbon.conf import logger_configuration
from tracarbon.emissions import CarbonEmission
from tracarbon.emissions import CarbonUsage
from tracarbon.emissions import CarbonUsageUnit
from tracarbon.exceptions import AWSSensorException
from tracarbon.exceptions import AzureSensorException
from tracarbon.exceptions import CloudProviderRegionIsMissing
from tracarbon.exceptions import CO2SignalAPIKeyIsMissing
from tracarbon.exceptions import CountryIsMissing
from tracarbon.exceptions import GCPSensorException
from tracarbon.exceptions import HardwareIOReportException
from tracarbon.exceptions import HardwareNoGPUDetectedException
from tracarbon.exceptions import HardwareRAPLException
from tracarbon.exceptions import TracarbonException
from tracarbon.exporters import Exporter
from tracarbon.exporters import JSONExporter
from tracarbon.exporters import Metric
from tracarbon.exporters import MetricGenerator
from tracarbon.exporters import MetricReport
from tracarbon.exporters import StdoutExporter
from tracarbon.exporters import Tag
from tracarbon.general_metrics import CarbonEmissionGenerator
from tracarbon.general_metrics import CarbonEmissionProcessGenerator
from tracarbon.general_metrics import EnergyConsumptionGenerator
from tracarbon.general_metrics import EnergyConsumptionProcessGenerator
from tracarbon.hardwares import EnergyUsageUnit
from tracarbon.hardwares import IOReportEnergy
from tracarbon.hardwares import Processes
from tracarbon.hardwares import ProcessUsage
from tracarbon.hardwares import UsageType
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
from tracarbon.locations import AWSLocation
from tracarbon.locations import AzureLocation
from tracarbon.locations import CarbonIntensityMetadata
from tracarbon.locations import CarbonIntensitySource
from tracarbon.locations import CloudLocation
from tracarbon.locations import Country
from tracarbon.locations import EmissionFactorType
from tracarbon.locations import GCPLocation
from tracarbon.locations import Location

if DATADOG_INSTALLED:
    from tracarbon.exporters import DatadogExporter as DatadogExporter

if PROMETHEUS_INSTALLED:
    from tracarbon.exporters import PrometheusExporter as PrometheusExporter

__all__ = [
    "AWSSensorException",
    "AWSEC2EnergyConsumption",
    "AWSLocation",
    "AMDRAPL",
    "AppleSiliconPowerMetrics",
    "AzureEnergyConsumption",
    "AzureLocation",
    "AzureSensorException",
    "CO2SignalAPIKeyIsMissing",
    "CarbonEmission",
    "CarbonEmissionGenerator",
    "CarbonEmissionProcessGenerator",
    "CarbonIntensityMetadata",
    "CarbonIntensitySource",
    "CarbonUsage",
    "CarbonUsageUnit",
    "CloudEnergyConsumption",
    "CloudLocation",
    "CloudProviderRegionIsMissing",
    "Country",
    "CountryIsMissing",
    "DATADOG_INSTALLED",
    "EmissionFactorType",
    "EnergyConsumption",
    "EnergyConsumptionGenerator",
    "EnergyConsumptionProcessGenerator",
    "EnergyUsage",
    "EnergyUsageUnit",
    "Exporter",
    "GCPEnergyConsumption",
    "GCPSensorException",
    "GCPLocation",
    "GPUInfo",
    "HardwareInfo",
    "HardwareNoGPUDetectedException",
    "IOReportEnergy",
    "HardwareIOReportException",
    "HardwareRAPLException",
    "JSONExporter",
    "KUBERNETES_INSTALLED",
    "LinuxEnergyConsumption",
    "Location",
    "MacEnergyConsumption",
    "Metric",
    "MetricGenerator",
    "MetricReport",
    "PROMETHEUS_INSTALLED",
    "ProcessUsage",
    "Processes",
    "RAPL",
    "Sensor",
    "StdoutExporter",
    "Tag",
    "Tracarbon",
    "TracarbonBuilder",
    "TracarbonConfiguration",
    "TracarbonException",
    "TracarbonReport",
    "UsageType",
    "WindowsEnergyConsumption",
    "check_optional_dependency",
    "logger_configuration",
]

if DATADOG_INSTALLED:
    __all__.append("DatadogExporter")

if PROMETHEUS_INSTALLED:
    __all__.append("PrometheusExporter")

# Resolve optional exports on access while keeping the static exports visible to tooling.
_PUBLIC_EXPORTS = __all__
del __all__

_KUBERNETES_EXPORTS = ("CarbonEmissionKubernetesGenerator", "EnergyConsumptionKubernetesGenerator", "Kubernetes")


def __getattr__(name: str) -> _Any:
    if name == "KUBERNETES_INSTALLED":
        return _conf.KUBERNETES_INSTALLED
    if name == "__all__":
        exports = _PUBLIC_EXPORTS + (list(_KUBERNETES_EXPORTS) if _conf.KUBERNETES_INSTALLED else [])
        globals()[name] = exports
        return exports
    if name in _KUBERNETES_EXPORTS and _conf.KUBERNETES_INSTALLED:
        from tracarbon import _kubernetes_metrics

        value = getattr(_kubernetes_metrics, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    exports = globals().get("__all__")
    if exports is None:
        exports = __getattr__("__all__")
    return sorted(set(globals()) | set(exports))
