![Alt text](logo.png?raw=true "Tracarbon logo")

[![doc](https://img.shields.io/badge/docs-python-blue.svg?style=flat-square)](https://fvaleye.github.io/tracarbon)
[![pypi](https://img.shields.io/pypi/v/tracarbon.svg?style=flat-square)](https://pypi.org/project/tracarbon/)
![example workflow](https://github.com/fvaleye/tracarbon/actions/workflows/build.yml/badge.svg)


## 📌 Overview
Tracarbon is a Python library that tracks your device's energy consumption and calculates your carbon emissions.

It detects your location and your device automatically before starting to export measurements to an exporter. 
It could be used as a CLI with already defined metrics or programmatically with the API by defining the metrics that you want to have.

Read more in this [article](https://medium.com/@florian.valeye/tracarbon-track-your-devices-carbon-footprint-fb051fcc9009).

## 📦 Where to get it

```sh
# Install Tracarbon
pip install tracarbon
```

```sh
# Install one or more exporters from the list
pip install 'tracarbon[datadog]'
```

### 🔌 Devices: energy consumption
| **Devices** |                                **Description**                                 |
|-------------|:------------------------------------------------------------------------------:|
| **Mac**     | ✅ Global energy consumption of your Mac (must be plugged into a wall adapter). |
| **Linux**   |                             ❌ Not yet implemented.                             |
| **Windows** |                             ❌ Not yet implemented.                             |

| **Cloud Provider** |                                                                                               **Description**                                                                                               |
|--------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------:|
| **AWS**            | ✅ Used the CPU usage with the EC2 instances carbon emissions datasets of [cloud-carbon-coefficients](https://github.com/cloud-carbon-footprint/cloud-carbon-coefficients/blob/main/data/aws-instances.csv). |
| **GCP**            |                                                                                           ❌ Not yet implemented.                                                                                            |
| **Azure**          |                                                                                           ❌ Not yet implemented.                                                                                            |


## 📡 Exporters
| **Exporter** |       **Description**        |
|--------------|:----------------------------:|
| **Stdout**   | Print the metrics in Stdout. |
| **Datadog**  | Send the metrics to Datadog. |

### 🗺️ Locations
| **Location** |                                         **Description**                                          | **Source**                                                                                                                                                    |
|--------------|:------------------------------------------------------------------------------------------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Europe**   | Static file of the European Environment Agency Emission for the co2g/kwh for European countries. | [EEA website](https://www.eea.europa.eu/data-and-maps/daviz/co2-emission-intensity-9#tab-googlechartid_googlechartid_googlechartid_googlechartid_chart_11111) |
| **France**   |               Get the co2g/kwh in near real-time using the RTE energy consumption.               | [RTE API](https://opendata.reseaux-energies.fr)                                                                                                               |
| **AWS**      |                 Static file of the AWS Grid emissions factors.                 | [cloud-carbon-coefficients](https://github.com/cloud-carbon-footprint/cloud-carbon-coefficients/blob/main/data/grid-emissions-factors-aws.csv)                |

### ⚙️ Configuration
| **Parameter**                     | **Description**                                                                |
|-----------------------------------|:-------------------------------------------------------------------------------|
| **TRACARBON_API_ACTIVATED**       | The activation of the real-time data collection of the carbon emission factor. |
| **TRACARBON_METRIC_PREFIX_NAME**  | The prefix to use in all the metrics name.                                     |
| **TRACARBON_INTERVAL_IN_SECONDS** | The interval in seconds to wait between the metrics evaluation.                |
| **TRACARBON_LOG_LEVEL**        | The level to use for displaying the logs.                                      |


## 🔎 Usage

**Command Line**
```sh
tracarbon run Stdout
```

**API**
```python
from tracarbon import CarbonEmission
from tracarbon.exporters import Metric, StdoutExporter

metric = Metric(
    name="co2_emission",
    value=CarbonEmission().run,
    tags=[],
)
exporter = StdoutExporter(metrics=[metric])
exporter.start()
# Your code
exporter.stop()

with exporter:
    # Your code
```

## 💻 Development

**Local: using Poetry**
```sh
make setup
make unit-test
```

## 🛡️ Licence
[Apache License 2.0](https://raw.githubusercontent.com/fvaleye/tracarbon/main/LICENSE.txt)

## 📚 Documentation
The documentation is hosted here: https://fvaleye.github.io/tracarbon/documentation
