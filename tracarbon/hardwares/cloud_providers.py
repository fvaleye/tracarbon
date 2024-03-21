from typing import Optional

import requests
from ec2_metadata import EC2Metadata
from ec2_metadata import ec2_metadata
from pydantic import BaseModel


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
        return AWS.is_ec2()

    @staticmethod
    def auto_detect() -> Optional["CloudProviders"]:
        """
        Autodetect the cloud provider.

        :return: the cloud provider detected
        """
        if CloudProviders.is_running_on_cloud_provider():
            return AWS(
                region_name=ec2_metadata.region,
                instance_type=ec2_metadata.instance_type,
            )
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
