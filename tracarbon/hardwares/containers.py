import os
from typing import Any
from typing import Iterator
from typing import List

from loguru import logger
from pydantic import BaseModel
from pydantic import PrivateAttr

from tracarbon.conf import KUBERNETES_INSTALLED
from tracarbon.exceptions import TracarbonException
from tracarbon.hardwares.hardware import HardwareInfo

__all__: list[str] = []

if KUBERNETES_INSTALLED:
    __all__ = ["Container", "Pod", "Kubernetes"]
    from kubernetes import config
    from kubernetes.client import CoreV1Api
    from kubernetes.client import CustomObjectsApi
    from kubernetes.utils.quantity import parse_quantity

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
                data["cpu_usage"] = float(parse_quantity(data["cpu_usage"])) / cores

            if isinstance(data["memory_usage"], str):
                data["memory_usage"] = float(parse_quantity(data["memory_usage"])) / memory_total

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

        namespaces: List[str] | None = None
        api: CustomObjectsApi
        node_name: str | None = None
        group: str = "metrics.k8s.io"
        version: str = "v1beta1"
        _core_api: CoreV1Api = PrivateAttr(default_factory=CoreV1Api)

        model_config = {
            "arbitrary_types_allowed": True,
        }

        def __init__(self, **data: Any) -> None:
            try:
                config.load_incluster_config()
            except Exception:
                config.load_kube_config()

            if "api" not in data:
                data["api"] = CustomObjectsApi()
            if not data.get("node_name"):
                data["node_name"] = os.environ.get("TRACARBON_KUBERNETES_NODE_NAME") or os.environ.get("NODE_NAME")
            if not data["node_name"]:
                logger.warning(
                    "NODE_NAME is not set, so the pods of every node in the cluster are attributed to this one. "
                    "Set NODE_NAME from spec.nodeName with the Downward API."
                )
            super().__init__(**data)

        def refresh_namespaces(self) -> None:
            """
            Refresh the names of the namespaces.
            """
            self.namespaces = [item.metadata.name for item in self._core_api.list_namespace().items]

        def _get_node_pod_keys(self, namespace: str | None) -> set[tuple[str, str]] | None:
            if not self.node_name:
                return None
            field_selector = f"spec.nodeName={self.node_name}"
            if namespace:
                pods = self._core_api.list_namespaced_pod(namespace=namespace, field_selector=field_selector)
            else:
                pods = self._core_api.list_pod_for_all_namespaces(field_selector=field_selector)
            return {(item.metadata.namespace, item.metadata.name) for item in pods.items}

        def get_pods_usage(self, namespace: str | None = None) -> Iterator[Pod]:
            """
            Yield pod usage for the configured node, or all nodes if unset.

            :param namespace: namespace to query, or None for all namespaces
            :return: pods with per-container CPU and memory usage
            """
            if namespace:
                self.refresh_namespaces()
                if self.namespaces and namespace not in self.namespaces:
                    raise TracarbonException(
                        ValueError(
                            f"The Kubernetes namespace {namespace} is not available "
                            f"in the namespaces {self.namespaces}."
                        )
                    )
                resource = self.api.list_namespaced_custom_object(
                    group=self.group, version=self.version, namespace=namespace, plural="pods"
                )
            else:
                resource = self.api.list_cluster_custom_object(group=self.group, version=self.version, plural="pods")
            node_pod_keys = self._get_node_pod_keys(namespace=namespace)
            for pod in resource["items"]:
                pod_name = pod["metadata"]["name"]
                pod_namespace = pod["metadata"]["namespace"]
                if node_pod_keys is not None and (pod_namespace, pod_name) not in node_pod_keys:
                    continue
                yield Pod(
                    name=pod_name,
                    namespace=pod_namespace,
                    containers=[
                        Container(
                            name=container["name"],
                            cpu_usage=container["usage"]["cpu"],
                            memory_usage=container["usage"]["memory"],
                        )
                        for container in pod["containers"]
                    ],
                )
