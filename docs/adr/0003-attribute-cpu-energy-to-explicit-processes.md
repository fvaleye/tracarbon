# Attribute CPU energy to explicit processes

* Status: Accepted
* Date: 2026-10-19
* Pull request: [#549](https://github.com/fvaleye/tracarbon/pull/549)

## Context and Problem Statement

Tracarbon measures the whole host, so it cannot tell what a single workload emits.

## Considered Options

* Keep host-level measurement only
* Attribute CPU energy and carbon to selected processes

## Decision Outcome

Chosen option: "Attribute CPU energy and carbon to selected processes", because it answers per-workload questions without new sensors.

A process tree's share is its CPU time divided by total CPU capacity, idle time included. Its power is that share times the host CPU power. The tree includes descendants. Only PIDs passed explicitly are tracked (`tracarbon run --pid`, `TracarbonBuilder().with_processes()`); Tracarbon does not discover processes. The metrics `energy_consumption_process_cpu` and `carbon_emission_process_cpu` go through every exporter.

### Consequences

* Good, because a share of total capacity is comparable across processes and hosts
* Good, because the same metrics work in every exporter
* Bad, because the attribution covers CPU only, not memory or GPU
