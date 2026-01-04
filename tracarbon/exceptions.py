__all__ = [
    "TracarbonException",
    "CountryIsMissing",
    "CloudProviderRegionIsMissing",
    "AWSSensorException",
    "GCPSensorException",
    "AzureSensorException",
    "HardwareRAPLException",
    "HardwareNoGPUDetectedException",
    "CO2SignalAPIKeyIsMissing",
]


class TracarbonException(Exception):
    """General Tracarbon Exception."""

    pass


class CountryIsMissing(TracarbonException):
    """The country is missing."""

    pass


class CloudProviderRegionIsMissing(TracarbonException):
    """The region of the cloud provider is missing."""

    pass


class AWSSensorException(TracarbonException):
    """Error in the AWS Sensor Error."""

    pass


class GCPSensorException(TracarbonException):
    """Error in the GCP Sensor."""

    pass


class AzureSensorException(TracarbonException):
    """Error in the Azure Sensor."""

    pass


class HardwareRAPLException(TracarbonException):
    """The hardware is not compatible with RAPL."""

    pass


class HardwareNoGPUDetectedException(TracarbonException):
    """The hardware does not have a GPU."""

    pass


class CO2SignalAPIKeyIsMissing(TracarbonException):
    """The C02 Signal API key is missing."""

    pass
