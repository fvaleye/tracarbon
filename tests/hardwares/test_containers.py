import pytest
from kubernetes import config
from kubernetes.client import CoreV1Api
from kubernetes.client import CustomObjectsApi
from kubernetes.client import V1Namespace
from kubernetes.client import V1NamespaceList
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1Pod
from kubernetes.client import V1PodList

from tracarbon import HardwareInfo
from tracarbon.hardwares.containers import Container
from tracarbon.hardwares.containers import Kubernetes
from tracarbon.hardwares.containers import Pod


@pytest.mark.parametrize(
    ("cpu_usage", "memory_usage", "expected_cpu", "expected_memory"),
    [
        ("1000000000n", "1048576Ki", 0.125, 0.125),
        ("1000000u", "1024Mi", 0.125, 0.125),
        ("1000m", "1Gi", 0.125, 0.125),
        ("1", "1073741824", 0.125, 0.125),
        ("0.5", "1G", 0.0625, 1000000000 / (8 * 1024**3)),
        ("1e0", "1073741824e0", 0.125, 0.125),
        ("0", "0", 0.0, 0.0),
        (0.25, 0.5, 0.25, 0.5),
        (1, 1, 1.0, 1.0),
    ],
)
def test_container_normalizes_kubernetes_quantities(mocker, cpu_usage, memory_usage, expected_cpu, expected_memory):
    mocker.patch.object(HardwareInfo, "get_number_of_cores", return_value=8)
    mocker.patch.object(HardwareInfo, "get_memory_total", return_value=8 * 1024**3)

    container = Container(name="worker", cpu_usage=cpu_usage, memory_usage=memory_usage)

    assert (container.cpu_usage, container.memory_usage) == pytest.approx((expected_cpu, expected_memory))


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
                "containers": [{"name": "shorty", "usage": {"cpu": "380444n", "memory": "3304Ki"}}],
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
    mocker.patch.object(HardwareInfo, "get_number_of_cores", return_value=number_of_cores)
    memory_total = 1000000000
    mocker.patch.object(HardwareInfo, "get_memory_total", return_value=memory_total)
    mocker.patch.object(CustomObjectsApi, "list_namespaced_custom_object", return_value=return_value)
    mocker.patch.object(
        CoreV1Api,
        "list_namespace",
        return_value=V1NamespaceList(items=[V1Namespace(metadata=V1ObjectMeta(name="default"))]),
    )
    mocker.patch.object(config, "load_kube_config", return_value=None)
    pods_usage_expected = [
        Pod(
            name="grafana-5745b58656-8q4q8",
            namespace="default",
            containers=[Container(name="grafana", cpu_usage=0.5, memory_usage=0.524288)],
        ),
        Pod(
            name="shorty-5469f85799-n4k2x",
            namespace="default",
            containers=[Container(name="shorty", cpu_usage=0.000190222, memory_usage=0.003383296)],
        ),
        Pod(
            name="subnet-router",
            namespace="default",
            containers=[Container(name="tailscale", cpu_usage=0.0070081, memory_usage=0.015269888)],
        ),
    ]

    kubernetes = Kubernetes()
    pods_usage = list(kubernetes.get_pods_usage())

    assert pods_usage == pods_usage_expected


def test_get_pods_usage_filters_by_node_name(mocker):
    return_value = {
        "kind": "PodMetricsList",
        "apiVersion": "metrics.k8s.io/v1beta1",
        "metadata": {},
        "items": [
            {
                "metadata": {
                    "name": "grafana-5745b58656-8q4q8",
                    "namespace": "default",
                },
                "timestamp": "2023-01-09T08:01:44Z",
                "window": "15s",
                "containers": [{"name": "grafana", "usage": {"cpu": "9559630n", "memory": "22244Ki"}}],
            },
            {
                "metadata": {
                    "name": "shorty-5469f85799-n4k2x",
                    "namespace": "default",
                },
                "timestamp": "2023-01-09T08:01:31Z",
                "window": "18s",
                "containers": [{"name": "shorty", "usage": {"cpu": "14016200n", "memory": "14912Ki"}}],
            },
        ],
    }
    number_of_cores = 2
    mocker.patch.object(HardwareInfo, "get_number_of_cores", return_value=number_of_cores)
    memory_total = 1000000000
    mocker.patch.object(HardwareInfo, "get_memory_total", return_value=memory_total)
    mocker.patch.object(CustomObjectsApi, "list_namespaced_custom_object", return_value=return_value)
    mocker.patch.object(
        CoreV1Api,
        "list_namespace",
        return_value=V1NamespaceList(items=[V1Namespace(metadata=V1ObjectMeta(name="default"))]),
    )
    list_namespaced_pod = mocker.patch.object(
        CoreV1Api,
        "list_namespaced_pod",
        return_value=V1PodList(
            items=[
                V1Pod(metadata=V1ObjectMeta(name="grafana-5745b58656-8q4q8")),
            ]
        ),
    )
    mocker.patch.object(config, "load_kube_config", return_value=None)

    kubernetes = Kubernetes(node_name="node-a")
    pods_usage = list(kubernetes.get_pods_usage())

    assert pods_usage == [
        Pod(
            name="grafana-5745b58656-8q4q8",
            namespace="default",
            containers=[Container(name="grafana", cpu_usage=0.004779815, memory_usage=0.022777856)],
        )
    ]
    list_namespaced_pod.assert_called_once_with(namespace="default", field_selector="spec.nodeName=node-a")


def test_kubernetes_uses_node_name_from_env(mocker, monkeypatch):
    mocker.patch.object(config, "load_kube_config", return_value=None)
    monkeypatch.setenv("NODE_NAME", "node-a")

    kubernetes = Kubernetes()

    assert kubernetes.node_name == "node-a"
