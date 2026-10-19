# Measure Linux CPU power as the package minus the integrated GPU

* Status: Accepted
* Date: 2026-10-19
* Pull request: [#548](https://github.com/fvaleye/tracarbon/pull/548)

## Context and Problem Statement

Linux CPU power was read from the RAPL `core` zone (PP0), which is wrong or absent on most current hardware.

## Considered Options

* Keep reading the `core` zone
* Report the package zone minus the `uncore` zone, the integrated GPU

## Decision Outcome

Chosen option: "Report the package zone minus the `uncore` zone", because the package is present on current hardware and the integrated GPU is measured separately.

The documented AMD powercap kernel floor moves from 5.8 to 5.11.

### Consequences

* Good, because CPU power is available on Xeons since Haswell-EP, which expose no `core` zone
* Good, because AMD reports all cores, while its `core` zone covers a single core
* Good, because CPU, GPU and memory power add up to the host power
* Bad, because `energy_consumption_cpu` rises for existing users, so dashboards and thresholds need a release note
