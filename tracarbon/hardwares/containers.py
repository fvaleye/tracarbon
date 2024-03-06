from typing import Any
from typing import Iterator
from typing import List
from typing import Optional

from pydantic import BaseModel

from tracarbon.conf import KUBERNETES_INSTALLED
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares.hardware import HardwareInfo

if KUBERNETES_INSTALLED:
    from kubernetes import config
    from kubernetes.client import CoreV1Api
    from kubernetes.client import CustomObjectsApi

    class Container(BaseModel):
        """
        Container of Kubernetes.
        """

        name: str
        cpu_usage: float  # in percentage of the total CPU
        memory_usage: float  # in percentage of the total memory

        def __init__(self, **data: Any) -> None:
            """
            Initialize the Contaniner values based on cpu and memory usages.
            """
            cores = HardwareInfo.get_number_of_cores()
            memory_total = HardwareInfo.get_memory_total()
            if isinstance(data["cpu_usage"], str):
                if "n" in data["cpu_usage"]:
                    data["cpu_usage"] = (float(data["cpu_usage"].replace("n", "")) / 1000000000) / cores
                elif "u" in data["cpu_usage"]:
                    data["cpu_usage"] = (float(data["cpu_usage"].replace("u", "")) / 1000000) / cores
                elif "m" in data["cpu_usage"]:
                    data["cpu_usage"] = (float(data["cpu_usage"].replace("m", "")) / 1000) / cores

            if isinstance(data["memory_usage"], str):
                if "Ki" in data["memory_usage"]:
                    data["memory_usage"] = (float(data["memory_usage"].replace("Ki", "")) * 1000) / memory_total
                elif "Mi" in data["memory_usage"]:
                    data["memory_usage"] = (float(data["memory_usage"].replace("Mi", "")) * 1000000) / memory_total
                elif "Gi" in data["memory_usage"]:
                    data["memory_usage"] = (float(data["memory_usage"].replace("Gi", "")) * 1000000000) / memory_total

            super().__init__(**data)

    class Pod(BaseModel):
        """
        Pod for Kubernetes.
        """

        name: str
        namespace: str
        containers: List[Container]

    class Kubernetes(BaseModel):
        """
        Kubernetes client.
        """

        namespaces: Optional[List[str]] = None
        api: CustomObjectsApi
        group: str = "metrics.k8s.io"
        version: str = "v1beta1"

        class Config:
            """Pydantic configuration."""

            arbitrary_types_allowed = True

        def __init__(self, **data: Any) -> None:
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()

            if "api" not in data:
                data["api"] = CustomObjectsApi()
            super().__init__(**data)

        def refresh_namespaces(self) -> None:
            """
            Refresh the names of the namespaces.
            """
            self.namespaces = [item.metadata.name for item in CoreV1Api().list_namespace().items]

        def get_pods_usage(self, namespace: Optional[str] = None) -> Iterator[Pod]:
            """
            Get Pods with usage.

            :param: namespaces: list of namespaces for getting the pods.
            :return: an iterator of the pods
            """
            self.refresh_namespaces()
            if namespace and self.namespaces and namespace not in self.namespaces:
                raise TracarbonException(
                    ValueError(
                        f"The Kubernetes namespace {namespace} is not available in the namespaces {self.namespaces}."
                    )
                )
            for n in self.namespaces:
                if namespace and namespace != n:
                    continue

                resource = self.api.list_namespaced_custom_object(
                    group=self.group,
                    version=self.version,
                    namespace=n,
                    plural="pods",
                )
                for pod in resource["items"]:
                    yield Pod(
                        name=pod["metadata"]["name"],
                        namespace=pod["metadata"]["namespace"],
                        containers=[
                            Container(
                                name=container["name"],
                                cpu_usage=container["usage"]["cpu"],
                                memory_usage=container["usage"]["memory"],
                            )
                            for container in pod["containers"]
                        ],
                    )
