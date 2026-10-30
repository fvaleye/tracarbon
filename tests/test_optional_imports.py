import pytest


@pytest.mark.parametrize("command", ["import tracarbon", "from tracarbon.cli import app; app(['--help'])"])
def test_host_imports_do_not_load_kubernetes(run_python, command):
    script = f"""
import sys
try:
    {command}
except SystemExit as error:
    assert error.code == 0
assert not any(name == 'kubernetes' or name.startswith('kubernetes.') for name in sys.modules)
"""

    assert run_python("-c", script) == ""


def test_kubernetes_exports_keep_their_public_import_paths(run_python):
    script = """
import pickle
import tracarbon
import tracarbon.general_metrics as metrics
import tracarbon.hardwares as hardware
from tracarbon import CarbonEmissionKubernetesGenerator, EnergyConsumptionKubernetesGenerator, Kubernetes
from tracarbon.hardwares import Container, Pod
from tracarbon.hardwares.containers import Kubernetes as DirectKubernetes
from kubernetes.client import CustomObjectsApi

assert Kubernetes is DirectKubernetes
assert Kubernetes is hardware.Kubernetes
assert EnergyConsumptionKubernetesGenerator is metrics.EnergyConsumptionKubernetesGenerator
assert CarbonEmissionKubernetesGenerator is metrics.CarbonEmissionKubernetesGenerator
assert EnergyConsumptionKubernetesGenerator.__module__ == 'tracarbon.general_metrics'
assert pickle.loads(pickle.dumps(EnergyConsumptionKubernetesGenerator)) is EnergyConsumptionKubernetesGenerator
assert Kubernetes.model_fields['api'].annotation is CustomObjectsApi
assert tracarbon.__all__ is tracarbon.__all__
assert hardware.__all__ is hardware.__all__
for module in (tracarbon, hardware):
    module.__all__.append('application_export')
    dir(module)
    assert 'application_export' in module.__all__
    module.__all__.remove('application_export')
for module in (tracarbon, hardware, metrics):
    namespace = {}
    exec(f'from {module.__name__} import *', namespace)
    assert namespace['Kubernetes'] is Kubernetes
    assert 'Kubernetes' in dir(module)
assert Container(name='worker', cpu_usage=0.25, memory_usage=0.5).cpu_usage == 0.25
assert Pod(name='worker', namespace='default', containers=[]).containers == []
"""

    assert run_python("-c", script) == ""


@pytest.mark.parametrize("broken_package", [False, True])
def test_unavailable_kubernetes_keeps_optional_exports_unavailable(run_python, tmp_path, broken_package):
    if broken_package:
        package = tmp_path / "kubernetes"
        package.mkdir()
        (package / "__init__.py").write_text("raise ImportError('missing Kubernetes dependency')\n")
    hidden_package = "" if broken_package else "sys.modules['kubernetes'] = None"
    script = f"""
import sys
{hidden_package}
import tracarbon
import tracarbon.conf as conf
import tracarbon.general_metrics as metrics
import tracarbon.hardwares as hardware
assert tracarbon.KUBERNETES_INSTALLED is False
assert conf.KUBERNETES_INSTALLED is False
assert conf.check_optional_dependency('kubernetes') is False
for module in (tracarbon, hardware, metrics):
    namespace = {{}}
    exec(f'from {{module.__name__}} import *', namespace)
    assert 'Kubernetes' not in namespace
    assert not hasattr(module, 'Kubernetes')
    assert 'Kubernetes' not in dir(module)
from tracarbon.cli import add_containers_generator, KUBERNETES_INSTALLED
assert KUBERNETES_INSTALLED is False
try:
    add_containers_generator(tracarbon.Country(name='fr', co2g_kwh=50))
except ImportError as error:
    assert str(error) == 'kubernetes optional dependency is not installed'
else:
    raise AssertionError('Kubernetes should be unavailable')
"""

    assert run_python("-c", script) == ""


def test_optional_availability_remains_boolean_and_exporters_remain_discoverable(run_python):
    script = """
import sys
import tracarbon
import tracarbon.conf as conf
from tracarbon.cli import list_exporters
assert 'kubernetes' not in sys.modules
assert set(list_exporters(displayed=False)) == {'Stdout', 'JSON', 'Datadog', 'Prometheus'}
from tracarbon.cli import KUBERNETES_INSTALLED as cli_installed
assert cli_installed is True
assert tracarbon.KUBERNETES_INSTALLED is True
assert conf.KUBERNETES_INSTALLED is True
assert 'kubernetes' in sys.modules
namespace = {}
exec('from tracarbon.conf import *', namespace)
assert namespace['KUBERNETES_INSTALLED'] is True
"""

    assert run_python("-c", script) == ""


def test_cli_wildcard_import_and_directory_keep_availability_flag(run_python):
    script = """
import tracarbon.cli as cli
namespace = {}
exec('from tracarbon.cli import *', namespace)
assert namespace['KUBERNETES_INSTALLED'] is True
assert 'KUBERNETES_INSTALLED' in dir(cli)
"""

    assert run_python("-c", script) == ""


def test_builder_keeps_its_process_generator_imports(run_python):
    script = """
from tracarbon import CarbonEmissionProcessGenerator, EnergyConsumptionProcessGenerator
from tracarbon.builder import CarbonEmissionProcessGenerator as Carbon
from tracarbon.builder import EnergyConsumptionProcessGenerator as Energy
assert Carbon is CarbonEmissionProcessGenerator
assert Energy is EnergyConsumptionProcessGenerator
"""

    assert run_python("-c", script) == ""
