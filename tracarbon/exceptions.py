class TracarbonException(Exception):
    """General Tracarbon Exception"""

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
