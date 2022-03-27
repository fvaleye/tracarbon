![Alt text](logo.png?raw=true "Tracarbon logo")

[![doc](https://img.shields.io/badge/docs-python-blue.svg?style=flat-square)](https://fvaleye.github.io/tracarbon)
[![pypi](https://img.shields.io/pypi/v/tracarbon.svg?style=flat-square)](https://pypi.org/project/tracarbon/)
![example workflow](https://github.com/fvaleye/tracarbon/actions/workflows/build.yml/badge.svg)


## 📌 Overview
Tracarbon is a Python library that tracks your device's power consumption and calculates your carbon emissions.

## 📦 Where to get it

```sh
# Install Tracarbon
pip install 'tracarbon'
```

```sh
# Install one or more exporters from the list
pip install 'tracarbon[datadog]'
```

### 🔌 Devices: energy consumption

| **Device**  |                 **Description**                 |
|-------------|:-----------------------------------------------:|
| **Mac**     | ✅ Battery energy consumption (must be plugged). |
| **Linux**   |             ❌ Not yet implemented.              |
| **Windows** |             ❌ Not yet implemented.              |

| **Cloud Provider** |                                                                    **Description**                                                                     |
|--------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------:|
| **AWS**            |✅ Estimation based on [cloud-carbon-coefficients](https://github.com/cloud-carbon-footprint/cloud-carbon-coefficients/blob/main/data/aws-instances.csv).|
| **GCP**            |                                                                 ❌ Not yet implemented.                                                                 |
| **Azure**          |                                                                 ❌ Not yet implemented.                                                                 |


## 📡 Exporters

| **Exporter** |                **Description**                |
|--------------|:-----------------------------------------:|
| **Stdout**   |       Print the metrics in Stdout.        |
| **Datadog**  |      Publish the metrics on Datadog.      |

### 🗺️ Locations


| **Location**                  |                  **Description**                   | **Source**                                                                                                                                                                                                                                |
|-------------------------------|:--------------------------------------------------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Europe** | European Environment Agency Emission co2g/kwh for European countries. | [EEA website](https://www.eea.europa.eu/data-and-maps/daviz/co2-emission-intensity-9#tab-googlechartid_googlechartid_googlechartid_googlechartid_chart_11111)                                                                             |
| **France**                    |      RTE energy consumption API in real-time.      | [RTE API](https://opendata.reseaux-energies.fr)                                                                                                                                                                                           |
| **AWS**                       |   AWS Grid emissions factors from cloud-carbon.    | [cloud-carbon-coefficients](https://github.com/cloud-carbon-footprint/cloud-carbon-coefficients/blob/main/data/grid-emissions-factors-aws.csv)                                                                                            |


## 🔎 Usage

**API**
```python
import asyncio

from tracarbon import CarbonEmission, EnergyConsumption, Country
from tracarbon.exporters import Metric, StdoutExporter
from tracarbon.hardwares import HardwareInfo

exporter = StdoutExporter()
metrics = list()
location = asyncio.run(Country.get_location())
energy_consumption = EnergyConsumption.from_platform()
platform = HardwareInfo.get_platform()
metrics.append(
    Metric(
        name="energy_consumption",
        value=energy_consumption.run,
        tags=[f"platform:{platform}", f"location:{location}"]
    )
)
metrics.append(
    Metric(
        name="co2_emission",
        value=CarbonEmission(energy_consumption=energy_consumption, location=location).run,
        tags=[f"platform:{platform}", f"location:{location}"]
    )
)
metrics.append(
    Metric(
        name="hardware_cpu_usage",
        value=HardwareInfo().get_cpu_usage,
        tags=[f"platform:{platform}", f"location:{location}"]
    )
)
metrics.append(
    Metric(
        name="hardware_memory_usage",
        value=HardwareInfo().get_memory_usage,
        tags=[f"platform:{platform}", f"location:{location}"]
    )
)
asyncio.run(exporter.launch_all(metrics=metrics))
```

**CLI**
```sh
tracarbon run Stdout
```

## 💻 Development

**Local**
```sh
make setup
make unit-test
```

## 🛡️ Licence
[Apache License 2.0](https://raw.githubusercontent.com/fvaleye/tracarbon/main/LICENSE.txt)

## 📚 Documentation
The documentation is hosted here: https://fvaleye.github.io/tracarbon/documentation
