![Tracarbon Logo](https://raw.githubusercontent.com/fvaleye/tracarbon/main/logo.png "Tracarbon logo")

![example workflow](https://github.com/fvaleye/tracarbon/actions/workflows/build.yml/badge.svg)
[![pypi](https://img.shields.io/pypi/v/tracarbon.svg?style=flat-square)](https://pypi.org/project/tracarbon/)
[![doc](https://img.shields.io/badge/docs-python-blue.svg?style=for-the-badgee)](https://fvaleye.github.io/tracarbon)
[![licence](https://img.shields.io/badge/license-Apache--2.0-green)](https://github.com/fvaleye/tracarbon/blob/main/LICENSE.txt)


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
pip install 'tracarbon[datadog,prometheus,kubernetes]'
```

### 🔌 Devices: energy consumption
| **Devices** |                                                                                                                                                           **Description**                                                                                                                                                            |
|-------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------:|
| Mac         |                                                                                                                            ✅ Global energy consumption of your Mac (must be plugged into a wall adapter).                                                                                                                            |
| Linux       | ⚠️ Only with [RAPL](https://web.eece.maine.edu/~vweaver/projects/rapl/). See [#1](https://github.com/fvaleye/tracarbon/issues/1). It works with containers on [Kubernetes](https://kubernetes.io/) using the [Metric API](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/#metrics-api) if available. |
| Windows     |                                                                                                                        ❌ Not yet implemented. See [#184](https://github.com/hubblo-org/scaphandre/pull/184).                                                                                                                         |

| **Cloud Provider** |                                                                                             **Description**                                                                                              |
|--------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------:|
| AWS                | ✅ Use the hardware's usage with the EC2 instances carbon emissions datasets of [cloud-carbon-coefficients](https://github.com/cloud-carbon-footprint/ccf-coefficients/blob/main/data/aws-instances.csv). |
| GCP                |                                                                                          ❌ Not yet implemented.                                                                                          |
| Azure              |                                                                                          ❌ Not yet implemented.                                                                                          |

## 📡 Exporters
| **Exporter** |          **Description**          |
|--------------|:---------------------------------:|
| Stdout       |   Print the metrics in Stdout.    |
| JSON         | Write the metrics in a JSON file. |
| Prometheus   |  Send the metrics to Prometheus.  |
| Datadog      |   Send the metrics to Datadog.    |

### 🗺️ Locations
| **Location** |                                                                              **Description**                                                                               | **Source**                                                                                                                                                    |
|--------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------:|:--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Worldwide    | Get the latest co2g/kwh in near real-time using the CO2Signal or ElectricityMaps APIs. See [here](http://api.electricitymap.org/v3/zones) for the list of available zones. | [CO2Signal API](https://www.co2signal.com) or [ElectricityMaps](https://static.electricitymaps.com/api/docs/index.html)                                       |
| Europe       |                                 Static file created from the European Environment Agency Emission for the co2g/kwh in European countries.                                  | [EEA website](https://www.eea.europa.eu/data-and-maps/daviz/co2-emission-intensity-9#tab-googlechartid_googlechartid_googlechartid_googlechartid_chart_11111) |
| AWS          |                                                               Static file of the AWS Grid emissions factors.                                                               | [cloud-carbon-coefficients](https://github.com/cloud-carbon-footprint/cloud-carbon-coefficients/blob/main/data/grid-emissions-factors-aws.csv)                |

### ⚙️ Configuration
The environment variables can be set from an environment file `.env`.

| **Parameter**                 | **Description**                                                                                                                                                                                                                                                                  |
|-------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| TRACARBON_CO2SIGNAL_API_KEY   | The api key received from [CO2Signal](https://www.co2signal.com) or [ElectricityMaps](https://static.electricitymaps.com/api/docs/index.html).                                                                                                                                   |
| TRACARBON_CO2SIGNAL_URL       | The url of [CO2Signal](https://docs.co2signal.com/#get-latest-by-country-code) is the default endpoint to retrieve the last known state of the zone, but it could be changed to [ElectricityMaps](https://static.electricitymaps.com/api/docs/index.html#live-carbon-intensity). |
| TRACARBON_METRIC_PREFIX_NAME  | The prefix to use in all the metrics name.                                                                                                                                                                                                                                       |
| TRACARBON_INTERVAL_IN_SECONDS | The interval in seconds to wait between the metrics evaluation.                                                                                                                                                                                                                  |
| TRACARBON_LOG_LEVEL           | The level to use for displaying the logs.                                                                                                                                                                                                                                        |

## 🔎 Usage

**Request your API key**
- Go to [CO2Signal](https://www.co2signal.com/) and get your free API key for non-commercial use, or go to [ElectricityMaps](https://static.electricitymaps.com/api/docs/index.html) for commercial use.
- This API is used to retrieve the last known carbon intensity (in gCO2eq/kWh) of electricity consumed in your location.
- Set your API key in the environment variables, in the `.env` file or directly in the configuration.
- If you would like to start without an API key, it's possible, the carbon intensity will be loaded statistically from a file.
- Launch Tracarbon 🚀

**Command Line**
```sh
tracarbon run
```

**API**
```python
from tracarbon import TracarbonBuilder, TracarbonConfiguration

configuration = TracarbonConfiguration() # Your configuration
tracarbon = TracarbonBuilder(configuration=configuration).build()
tracarbon.start()
# Your code
tracarbon.stop()

with tracarbon:
    # Your code

report = tracarbon.report() # Get the report
```

## 💻 Development

**Local: using Poetry**
```sh
make init
make test-unit
```

## 🛡️ Licence
[Apache License 2.0](https://raw.githubusercontent.com/fvaleye/tracarbon/main/LICENSE.txt)

## 📚 Documentation
The documentation is hosted here: https://fvaleye.github.io/tracarbon/documentation
