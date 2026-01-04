from typing import ClassVar
from typing import Dict
from typing import Optional

import requests
from ec2_metadata import EC2Metadata
from ec2_metadata import ec2_metadata
from pydantic import BaseModel

__all__ = [
    "CloudProviders",
    "AWS",
    "GCP",
    "Azure",
]


class CloudProviders(BaseModel):
    """The Cloud Provider interface."""

    instance_type: str
    region_name: str

    @staticmethod
    def is_running_on_cloud_provider() -> bool:
        """
        Check if it's running on a known cloud provider.

        :return: if it's running on a known cloud provider
        """
        return AWS.is_ec2() or GCP.is_gcp() or Azure.is_azure()

    @staticmethod
    def auto_detect() -> Optional["CloudProviders"]:
        """
        Autodetect the cloud provider.

        :return: the cloud provider detected
        """
        if AWS.is_ec2():
            return AWS(
                region_name=ec2_metadata.region,
                instance_type=ec2_metadata.instance_type,
            )
        if GCP.is_gcp():
            return GCP.from_metadata()
        if Azure.is_azure():
            return Azure.from_metadata()
        return None


class AWS(CloudProviders):
    """The Cloud Provider: AWS."""

    @staticmethod
    def is_ec2() -> bool:
        """
        Check if it's running on an AWS EC2 instance based on metadata.

        :return: is a EC2
        """
        try:
            ec2_metadata = EC2Metadata()
            requests.head(ec2_metadata.service_url, timeout=1)
        except Exception:
            return False
        return True


class GCP(CloudProviders):
    """The Cloud Provider: Google Cloud Platform."""

    METADATA_URL: ClassVar[str] = "http://metadata.google.internal/computeMetadata/v1/"
    METADATA_HEADERS: ClassVar[Dict[str, str]] = {"Metadata-Flavor": "Google"}

    @staticmethod
    def is_gcp() -> bool:
        """
        Check if it's running on a GCP Compute Engine instance based on metadata.

        :return: is a GCP instance
        """
        try:
            response = requests.get(
                f"{GCP.METADATA_URL}instance/zone",
                headers=GCP.METADATA_HEADERS,
                timeout=1,
            )
            return response.status_code == 200
        except Exception:
            return False

    @classmethod
    def from_metadata(cls) -> "GCP":
        """
        Create GCP instance from metadata server.

        :return: GCP cloud provider with instance type and region
        """
        headers = cls.METADATA_HEADERS

        # GET /computeMetadata/v1/instance/machine-type
        # Returns: projects/123456/machineTypes/n2-standard-4
        machine_type_response = requests.get(
            f"{cls.METADATA_URL}instance/machine-type",
            headers=headers,
            timeout=5,
        )
        machine_type = machine_type_response.text.split("/")[-1]

        # GET /computeMetadata/v1/instance/zone
        # Returns: projects/123456/zones/us-central1-a
        zone_response = requests.get(
            f"{cls.METADATA_URL}instance/zone",
            headers=headers,
            timeout=5,
        )
        zone = zone_response.text.split("/")[-1]
        # Extract region from zone (e.g., us-central1-a -> us-central1)
        # Zone format is typically: region-zone_letter (e.g., us-central1-a, europe-west1-b)
        zone_parts = zone.split("-")
        if len(zone_parts) < 2:
            # Fallback: use zone as region if format is unexpected
            region = zone
        else:
            # Remove the last part (zone letter) to get the region
            region = "-".join(zone_parts[:-1])

        return cls(instance_type=machine_type, region_name=region)


class Azure(CloudProviders):
    """The Cloud Provider: Microsoft Azure."""

    IMDS_URL: ClassVar[str] = "http://169.254.169.254/metadata/instance"
    API_VERSION: ClassVar[str] = "2021-02-01"

    @staticmethod
    def is_azure() -> bool:
        """
        Check if it's running on an Azure VM based on IMDS.

        :return: is an Azure VM
        """
        try:
            response = requests.get(
                f"{Azure.IMDS_URL}?api-version={Azure.API_VERSION}",
                headers={"Metadata": "true"},
                timeout=1,
            )
            return response.status_code == 200
        except Exception:
            return False

    @classmethod
    def from_metadata(cls) -> "Azure":
        """
        Create Azure instance from IMDS.

        :return: Azure cloud provider with VM size and location
        """
        response = requests.get(
            f"{cls.IMDS_URL}?api-version={cls.API_VERSION}",
            headers={"Metadata": "true"},
            timeout=5,
        )
        data = response.json()

        vm_size = data["compute"]["vmSize"]
        location = data["compute"]["location"]

        return cls(instance_type=vm_size, region_name=location)
