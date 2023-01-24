from kubernetes import config
from kubernetes.client import (
    CoreV1Api,
    CustomObjectsApi,
    V1Namespace,
    V1NamespaceList,
    V1ObjectMeta,
)

from tracarbon import HardwareInfo
from tracarbon.hardwares.containers import Container, Kubernetes, Pod


def test_get_pods_usage(mocker):
    return_value = {
        "kind": "PodMetricsList",
        "apiVersion": "metrics.k8s.io/v1beta1",
        "metadata": {},
        "items": [
            {
                "metadata": {
                    "name": "grafana-5745b58656-8q4q8",
                    "namespace": "default",
                    "creationTimestamp": "2023-01-09T08:01:49Z",
                    "labels": {
                        "app.kubernetes.io/instance": "grafana",
                        "app.kubernetes.io/name": "grafana",
                        "pod-template-hash": "5745b58656",
                    },
                },
                "timestamp": "2023-01-09T08:01:44Z",
                "window": "15s",
                "containers": [
                    {
                        "name": "grafana",
                        "usage": {"cpu": "1000m", "memory": "500Mi"},
                    }
                ],
            },
            {
                "metadata": {
                    "name": "shorty-5469f85799-n4k2x",
                    "namespace": "default",
                    "creationTimestamp": "2023-01-09T08:01:49Z",
                    "labels": {
                        "app.kubernetes.io/instance": "shorty",
                        "app.kubernetes.io/name": "shorty",
                        "pod-template-hash": "5469f85799",
                    },
                },
                "timestamp": "2023-01-09T08:01:31Z",
                "window": "18s",
                "containers": [
                    {"name": "shorty", "usage": {"cpu": "380444n", "memory": "3304Ki"}}
                ],
            },
            {
                "metadata": {
                    "name": "subnet-router",
                    "namespace": "default",
                    "creationTimestamp": "2023-01-09T08:01:49Z",
                    "labels": {"app": "tailscale"},
                },
                "timestamp": "2023-01-09T08:01:35Z",
                "window": "15s",
                "containers": [
                    {
                        "name": "tailscale",
                        "usage": {"cpu": "14016200n", "memory": "14912Ki"},
                    }
                ],
            },
        ],
    }
    number_of_cores = 2
    mocker.patch.object(
        HardwareInfo, "get_number_of_cores", return_value=number_of_cores
    )
    memory_total = 1000000000
    mocker.patch.object(HardwareInfo, "get_memory_total", return_value=memory_total)
    mocker.patch.object(
        CustomObjectsApi, "list_namespaced_custom_object", return_value=return_value
    )
    mocker.patch.object(
        CoreV1Api,
        "list_namespace",
        return_value=V1NamespaceList(
            items=[V1Namespace(metadata=V1ObjectMeta(name="default"))]
        ),
    )
    mocker.patch.object(config, "load_kube_config", return_value=None)
    pods_usage_expected = [
        Pod(
            name="grafana-5745b58656-8q4q8",
            namespace="default",
            containers=[Container(name="grafana", cpu_usage=0.5, memory_usage=0.5)],
        ),
        Pod(
            name="shorty-5469f85799-n4k2x",
            namespace="default",
            containers=[
                Container(name="shorty", cpu_usage=0.000190222, memory_usage=0.003304)
            ],
        ),
        Pod(
            name="subnet-router",
            namespace="default",
            containers=[
                Container(name="tailscale", cpu_usage=0.0070081, memory_usage=0.014912)
            ],
        ),
    ]

    kubernetes = Kubernetes()
    pods_usage = list(kubernetes.get_pods_usage())

    assert pods_usage == pods_usage_expected
