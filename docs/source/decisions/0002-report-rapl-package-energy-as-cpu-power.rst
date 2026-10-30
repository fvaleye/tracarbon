Report RAPL package energy as CPU power
=======================================

:Status: Accepted
:Date: 2026-10-30

Context
-------

Linux RAPL exposes a package zone per socket and, depending on the processor, core
(PP0), uncore (PP1) and DRAM zones. On Intel client parts, uncore is the integrated
GPU and lies inside the package. Intel Xeons since Haswell-EP expose no usable core
zone, Granite Rapids exposes only package and memory, and the AMD core zone covers a
single core.

Tracarbon reports CPU power and shares it among processes and containers by CPU time.
Version 0.14.0 reported the package minus uncore
(`#548 <https://github.com/fvaleye/tracarbon/issues/548>`_).

Decision
--------

Report the sum of package counters as CPU power. Keep uncore as GPU power and DRAM as
memory power. Host stays package plus DRAM, so the integrated GPU is counted once.

Every RAPL platform exposes the package, so CPU is the same counter everywhere and
needs no derived value.

Alternatives
------------

* Package minus uncore keeps integrated GPU work out of CPU-time shares, but only on
  Intel client parts, and derives CPU from two counters read at different instants.
* Core (PP0) is missing on recent Xeons and covers a single core on AMD.

Consequences
------------

On processors with an integrated GPU, CPU power includes GPU work, and CPU-time shares
assign that energy to processes and containers. CPU and GPU readings overlap, so
``host`` is the total to compare.
