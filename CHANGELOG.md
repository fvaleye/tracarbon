# Changelog

## [0.15.0](https://github.com/fvaleye/tracarbon/compare/v0.14.0...v0.15.0) (2026-10-29)


### Features

* **cli:** measure a command with tracarbon exec ([#557](https://github.com/fvaleye/tracarbon/issues/557)) ([c59caef](https://github.com/fvaleye/tracarbon/commit/c59caef7f52f9e9fbec2069df449af83aaddaebe))


### Bug Fixes

* fix stale macos energy readings ([#556](https://github.com/fvaleye/tracarbon/issues/556)) ([d7536ae](https://github.com/fvaleye/tracarbon/commit/d7536ae6bd15cad0760ae87341e68c9fa8bf98a4))


### Dependencies

* **deps:** Bump astral-sh/setup-uv from 10.3.0 to 10.3.2 ([#554](https://github.com/fvaleye/tracarbon/issues/554)) ([9e232b8](https://github.com/fvaleye/tracarbon/commit/9e232b803b12843cc69b7cb403ac818bd39dbf5d))

## [0.14.0](https://github.com/fvaleye/tracarbon/compare/v0.13.0...v0.14.0) (2026-10-19)


### Features

* **processes:** attribute CPU energy and carbon to processes ([#549](https://github.com/fvaleye/tracarbon/issues/549)) ([bc17b84](https://github.com/fvaleye/tracarbon/commit/bc17b84a37e80c5c9a1dbf794ddffccc8c9acc7e))


### Bug Fixes

* **rapl:** measure CPU power as the package without the integrated GPU ([#548](https://github.com/fvaleye/tracarbon/issues/548)) ([22171f6](https://github.com/fvaleye/tracarbon/commit/22171f631312b399b78dbf64f747b1c9a73eec4f))


### Dependencies

* **deps-dev:** Update datadog requirement from &lt;0.55,&gt;=0.44 to &gt;=0.44,&lt;0.56 ([#544](https://github.com/fvaleye/tracarbon/issues/544)) ([c5ed638](https://github.com/fvaleye/tracarbon/commit/c5ed638f6e549db64609a4792d78630cbc5c4af1))
* **deps-dev:** Update kubernetes requirement from &lt;37.0,&gt;=26.1 to &gt;=26.1,&lt;38.0 ([#546](https://github.com/fvaleye/tracarbon/issues/546)) ([65ce745](https://github.com/fvaleye/tracarbon/commit/65ce745a62f5876a73766f13ea52366d599e5c73))
* **deps-dev:** Update ruff requirement from &lt;0.17.0,&gt;=0.15.10 to &gt;=0.15.10,&lt;0.18.0 ([#545](https://github.com/fvaleye/tracarbon/issues/545)) ([d8b328d](https://github.com/fvaleye/tracarbon/commit/d8b328da92cd36c624a30a2dada1d948f157c9a0))
* **deps:** Bump astral-sh/setup-uv from 10.2.0 to 10.3.0 ([#547](https://github.com/fvaleye/tracarbon/issues/547)) ([256921a](https://github.com/fvaleye/tracarbon/commit/256921a7274acc061267b9c1c2286df5b7820022))


## [0.13.0](https://github.com/fvaleye/tracarbon/compare/v0.12.0...v0.13.0) (2026-09-28)


### Changes

* Refresh readme layout ([#534](https://github.com/fvaleye/tracarbon/issues/534))
* Harden packaging and deployment ([#536](https://github.com/fvaleye/tracarbon/issues/536))
* Add cumulative carbon counters and JSON Lines export ([#537](https://github.com/fvaleye/tracarbon/issues/537))
* Correct CPU sampling and power estimates ([#538](https://github.com/fvaleye/tracarbon/issues/538))
* Behave as an embedded library ([#539](https://github.com/fvaleye/tracarbon/issues/539))
* Bundle keyless carbon intensity ([#540](https://github.com/fvaleye/tracarbon/issues/540))
* Keep the collection loop running ([#541](https://github.com/fvaleye/tracarbon/issues/541))
* Harden the hardware readings ([#542](https://github.com/fvaleye/tracarbon/issues/542))


## [0.12.0](https://github.com/fvaleye/tracarbon/compare/v0.11.1...v0.12.0) (2026-09-07)


### Bug Fixes

* **cloud:** validate EC2 metadata before selecting AWS ([#528](https://github.com/fvaleye/tracarbon/issues/528))
* **gpu:** include NVIDIA power in Linux host totals ([#529](https://github.com/fvaleye/tracarbon/issues/529))


### Changes

* Finalize measurement reports ([#530](https://github.com/fvaleye/tracarbon/issues/530))
* Measure local llm with examples ([#531](https://github.com/fvaleye/tracarbon/issues/531))
* docs: list Tracarbon citations ([#533](https://github.com/fvaleye/tracarbon/issues/533))


## [0.11.1](https://github.com/fvaleye/tracarbon/compare/v0.11.0...v0.11.1) (2026-09-05)


### Bug Fixes

* **prometheus:** remove stale container series after collection ([#523](https://github.com/fvaleye/tracarbon/issues/523))
* **kubernetes:** normalize resource quantities ([#525](https://github.com/fvaleye/tracarbon/issues/525))
* **exporters:** restart measurement runs safely ([#526](https://github.com/fvaleye/tracarbon/issues/526))
* **locations:** expire carbon intensity across sampling loops ([#524](https://github.com/fvaleye/tracarbon/issues/524))


## [0.11.0](https://github.com/fvaleye/tracarbon/compare/V0.10.3...v0.11.0) (2026-09-05)


### Bug Fixes

* restore runtime measurement correctness ([#512](https://github.com/fvaleye/tracarbon/issues/512))
* **gpu:** keep a failing GPU probe from killing the run ([#518](https://github.com/fvaleye/tracarbon/issues/518))
* correct the energy the measurements report ([#520](https://github.com/fvaleye/tracarbon/issues/520))


### Changes

* Fix Kubernetes container metric node scoping ([#510](https://github.com/fvaleye/tracarbon/issues/510))
* Report total carbon emitted on stop ([#517](https://github.com/fvaleye/tracarbon/issues/517))
* Tell a restarted energy counter from one that wrapped ([#519](https://github.com/fvaleye/tracarbon/issues/519))
* Read apple silicon energy counters ([#521](https://github.com/fvaleye/tracarbon/issues/521))


### Dependencies

* build(deps): Update asyncer requirement from <0.0.18,>=0.0.5 to >=0.0.5,<0.0.19 ([#511](https://github.com/fvaleye/tracarbon/issues/511))
* build(deps): Update typer requirement from <0.27,>=0.7 to >=0.7,<0.28 ([#513](https://github.com/fvaleye/tracarbon/issues/513))
* build(deps-dev): Update ruff requirement from <0.16.0,>=0.15.10 to >=0.15.10,<0.17.0 ([#514](https://github.com/fvaleye/tracarbon/issues/514))
* build(deps-dev): Update datadog requirement from <0.53,>=0.44 to >=0.44,<0.54 ([#515](https://github.com/fvaleye/tracarbon/issues/515))
* build(deps-dev): Update prometheus-client requirement from <0.26,>=0.16 to >=0.16,<0.27 ([#516](https://github.com/fvaleye/tracarbon/issues/516))


## [0.10.3](https://github.com/fvaleye/tracarbon/compare/v0.10.2...V0.10.3) (2026-06-26)


### Changes

* Classify Intel RAPL domains ([#503](https://github.com/fvaleye/tracarbon/issues/503))
* Fix Python compatibility checks ([#504](https://github.com/fvaleye/tracarbon/issues/504))
* Cache cloud provider detection ([#505](https://github.com/fvaleye/tracarbon/issues/505))
* Use Electricity Maps v4 ([#506](https://github.com/fvaleye/tracarbon/issues/506))
* Stabilize Prometheus container metrics ([#507](https://github.com/fvaleye/tracarbon/issues/507))
* Surface carbon intensity metadata ([#508](https://github.com/fvaleye/tracarbon/issues/508))


### Dependencies

* build(deps-dev): Update pydata-sphinx-theme requirement from <0.19.0,>=0.14.4 to >=0.14.4,<0.20.0 ([#502](https://github.com/fvaleye/tracarbon/issues/502))


## [0.10.2](https://github.com/fvaleye/tracarbon/compare/v0.10.1...v0.10.2) (2026-06-17)


### Bug Fixes

* declare requests as a runtime dependency ([#500](https://github.com/fvaleye/tracarbon/issues/500))


### Dependencies

* build(deps-dev): Update kubernetes requirement from <36.0,>=26.1 to >=26.1,<37.0 ([#496](https://github.com/fvaleye/tracarbon/issues/496))
* build(deps-dev): Update pydata-sphinx-theme requirement from <0.18.0,>=0.14.4 to >=0.14.4,<0.19.0 ([#497](https://github.com/fvaleye/tracarbon/issues/497))
* build(deps-dev): Update pytest-asyncio requirement from <1.4.0,>=0.24.0 to >=0.24.0,<1.5.0 ([#499](https://github.com/fvaleye/tracarbon/issues/499))
* build(deps): Update typer requirement from <0.26,>=0.7 to >=0.7,<0.27 ([#498](https://github.com/fvaleye/tracarbon/issues/498))


## [0.10.1](https://github.com/fvaleye/tracarbon/compare/v0.10.0...v0.10.1) (2026-05-18)


### Bug Fixes

* Update uv.lock for ty latest version ([#483](https://github.com/fvaleye/tracarbon/issues/483))


### Changes

* chore: python 3.10 ([#485](https://github.com/fvaleye/tracarbon/issues/485))
* Upgrade dependencies and IP geolocation token ([#494](https://github.com/fvaleye/tracarbon/issues/494))


### Dependencies

* build(deps-dev): Update ruff requirement from <0.15.0,>=0.11.13 to >=0.11.13,<0.16.0 ([#479](https://github.com/fvaleye/tracarbon/issues/479))
* build(deps): Update asyncer requirement from <0.0.13,>=0.0.5 to >=0.0.5,<0.0.14 ([#481](https://github.com/fvaleye/tracarbon/issues/481))
* build(deps): Update typer requirement from <0.22,>=0.7 to >=0.7,<0.24 ([#480](https://github.com/fvaleye/tracarbon/issues/480))
* build(deps): Update asyncer requirement from <0.0.14,>=0.0.5 to >=0.0.5,<0.0.15 ([#482](https://github.com/fvaleye/tracarbon/issues/482))
* build(deps-dev): Update prometheus-client requirement from <0.25,>=0.16 to >=0.16,<0.26 ([#484](https://github.com/fvaleye/tracarbon/issues/484))
* build(deps): Update ec2-metadata requirement from <3.0.0,>=2.14.0 to >=2.14.0,<4.0.0 ([#490](https://github.com/fvaleye/tracarbon/issues/490))
* build(deps-dev): Update pytest requirement from <9.0.0,>=8.4.0 to >=8.4.0,<10.0.0 ([#489](https://github.com/fvaleye/tracarbon/issues/489))
* build(deps-dev): Update pydata-sphinx-theme requirement from <0.17.0,>=0.14.4 to >=0.14.4,<0.18.0 ([#487](https://github.com/fvaleye/tracarbon/issues/487))
* build(deps): Update typer requirement from <0.24,>=0.7 to >=0.7,<0.25 ([#488](https://github.com/fvaleye/tracarbon/issues/488))
* build(deps): Update asyncer requirement from <0.0.15,>=0.0.5 to >=0.0.5,<0.0.18 ([#486](https://github.com/fvaleye/tracarbon/issues/486))
* build(deps): Update typer requirement from <0.25,>=0.7 to >=0.7,<0.26 ([#493](https://github.com/fvaleye/tracarbon/issues/493))
* build(deps-dev): Update sphinx requirement from <8.0.0,>=7.4.7 to >=7.4.7,<9.0.0 ([#492](https://github.com/fvaleye/tracarbon/issues/492))
* build(deps-dev): Update pytest-asyncio requirement from <1.3.0,>=0.24.0 to >=0.24.0,<1.4.0 ([#491](https://github.com/fvaleye/tracarbon/issues/491))


## [0.10.0](https://github.com/fvaleye/tracarbon/compare/v0.9.1...v0.10.0) (2026-02-07)


### Features

* **cloud:** add GCP and Azure carbon emission tracking using new rerentials ([#471](https://github.com/fvaleye/tracarbon/issues/471))
* **sensor:** add Apple Silicon powermetrics for per-component energy measurement ([#476](https://github.com/fvaleye/tracarbon/issues/476))
* **api:** add Electricity Maps API v3 support with emission factor types ([#477](https://github.com/fvaleye/tracarbon/issues/477))


### Changes

* chore: bump version to 0.10.0 ([#478](https://github.com/fvaleye/tracarbon/issues/478))


### Dependencies

* build(deps-dev): Update prometheus-client requirement from <0.24,>=0.16 to >=0.16,<0.25 ([#473](https://github.com/fvaleye/tracarbon/issues/473))
* build(deps-dev): Update kubernetes requirement from <35.0,>=26.1 to >=26.1,<36.0 ([#474](https://github.com/fvaleye/tracarbon/issues/474))
* build(deps): Bump urllib3 from 2.5.0 to 2.6.3 ([#475](https://github.com/fvaleye/tracarbon/issues/475))


## [0.9.1](https://github.com/fvaleye/tracarbon/compare/v0.9.0...v0.9.1) (2026-01-04)


### Features

* **cloud:** add GCP and Azure carbon emission tracking using new rerentials ([#471](https://github.com/fvaleye/tracarbon/issues/471))


### Changes

* chore: bump version to 0.9.1 ([#472](https://github.com/fvaleye/tracarbon/issues/472))


## [0.9.0](https://github.com/fvaleye/tracarbon/compare/v0.8.0...v0.9.0) (2026-01-03)


### Features

* **sensor:** add AMD RAPL sensor ([#468](https://github.com/fvaleye/tracarbon/issues/468))
* **gpu:** add AMD, Apple Silicon support and multi-GPU detection wit… ([#469](https://github.com/fvaleye/tracarbon/issues/469))


### Bug Fixes

* **core:** several improvements and bug fixes with latest updates of Pydantic ([#449](https://github.com/fvaleye/tracarbon/issues/449))
* **referential:** update EU CO2 emission intensity data to 2022 ([#467](https://github.com/fvaleye/tracarbon/issues/467))


### Changes

* chore(typecheck): from mypy to ty for typechecking ([#470](https://github.com/fvaleye/tracarbon/issues/470))


### Dependencies

* build(deps-dev): Bump ruff from 0.11.13 to 0.12.5 ([#442](https://github.com/fvaleye/tracarbon/issues/442))
* build(deps-dev): Bump pytest-asyncio from 0.24.0 to 1.1.0 ([#440](https://github.com/fvaleye/tracarbon/issues/440))
* build(deps-dev): Bump pytest-cov from 5.0.0 to 6.2.1 ([#435](https://github.com/fvaleye/tracarbon/issues/435))
* build(deps): Bump autodoc-pydantic from 1.9.1 to 2.2.0 ([#445](https://github.com/fvaleye/tracarbon/issues/445))
* build(deps): Update pydata-sphinx-theme requirement from <0.15.0,>=0.14.4 to >=0.14.4,<0.17.0 ([#446](https://github.com/fvaleye/tracarbon/issues/446))
* build(deps): Update datadog requirement from <0.52,>=0.44 to >=0.44,<0.53 ([#447](https://github.com/fvaleye/tracarbon/issues/447))
* build(deps): Update typer requirement from <0.17,>=0.7 to >=0.7,<0.18 ([#450](https://github.com/fvaleye/tracarbon/issues/450))
* build(deps): Update pytest-cov requirement from <7.0.0,>=5.0.0 to >=5.0.0,<8.0.0 ([#452](https://github.com/fvaleye/tracarbon/issues/452))
* build(deps): Update pytest-asyncio requirement from <1.2.0,>=0.24.0 to >=0.24.0,<1.3.0 ([#451](https://github.com/fvaleye/tracarbon/issues/451))
* build(deps): Update ruff requirement from <0.13.0,>=0.11.13 to >=0.11.13,<0.14.0 ([#453](https://github.com/fvaleye/tracarbon/issues/453))
* build(deps): Update prometheus-client requirement from <0.23,>=0.16 to >=0.16,<0.24 ([#454](https://github.com/fvaleye/tracarbon/issues/454))
* build(deps): Update typer requirement from <0.18,>=0.7 to >=0.7,<0.20 ([#455](https://github.com/fvaleye/tracarbon/issues/455))
* build(deps): Update kubernetes requirement from <34.0,>=26.1 to >=26.1,<35.0 ([#457](https://github.com/fvaleye/tracarbon/issues/457))
* build(deps): Update ruff requirement from <0.14.0,>=0.11.13 to >=0.11.13,<0.15.0 ([#460](https://github.com/fvaleye/tracarbon/issues/460))
* build(deps): Update aiofiles requirement from <25.0,>=23.2 to >=23.2,<26.0 ([#459](https://github.com/fvaleye/tracarbon/issues/459))
* build(deps): Update types-aiofiles requirement from <25.0.0,>=24.1.0 to >=24.1.0,<26.0.0 ([#458](https://github.com/fvaleye/tracarbon/issues/458))
* build(deps): Update asyncer requirement from <0.0.9,>=0.0.5 to >=0.0.5,<0.0.10 ([#456](https://github.com/fvaleye/tracarbon/issues/456))
* build(deps): Update typer requirement from <0.20,>=0.7 to >=0.7,<0.21 ([#462](https://github.com/fvaleye/tracarbon/issues/462))
* build(deps): Update asyncer requirement from <0.0.10,>=0.0.5 to >=0.0.5,<0.0.11 ([#461](https://github.com/fvaleye/tracarbon/issues/461))
* build(deps): Update python-dotenv requirement from <1.2,>=0.21 to >=0.21,<1.3 ([#463](https://github.com/fvaleye/tracarbon/issues/463))
* build(deps): Update asyncer requirement from <0.0.11,>=0.0.5 to >=0.0.5,<0.0.13 ([#465](https://github.com/fvaleye/tracarbon/issues/465))
* build(deps): Update typer requirement from <0.21,>=0.7 to >=0.7,<0.22 ([#466](https://github.com/fvaleye/tracarbon/issues/466))


## [0.8.0](https://github.com/fvaleye/tracarbon/compare/v0.7.5...v0.8.0) (2025-07-31)


### Bug Fixes

* metrics appear when launching with the CLI ([#423](https://github.com/fvaleye/tracarbon/issues/423))


### Changes

* chore(uv): use uv instead of using poetry ([#443](https://github.com/fvaleye/tracarbon/issues/443))


### Dependencies

* build(deps-dev): Bump ruff from 0.8.5 to 0.8.6 ([#405](https://github.com/fvaleye/tracarbon/issues/405))
* build(deps): Bump pydantic from 1.10.19 to 1.10.21 ([#409](https://github.com/fvaleye/tracarbon/issues/409))
* build(deps-dev): Bump ruff from 0.8.6 to 0.9.3 ([#411](https://github.com/fvaleye/tracarbon/issues/411))
* build(deps-dev): Bump ruff from 0.9.3 to 0.9.5 ([#414](https://github.com/fvaleye/tracarbon/issues/414))
* build(deps): Bump datadog from 0.50.2 to 0.51.0 ([#412](https://github.com/fvaleye/tracarbon/issues/412))
* build(deps-dev): Bump ruff from 0.9.5 to 0.9.7 ([#418](https://github.com/fvaleye/tracarbon/issues/418))
* build(deps): Bump psutil from 6.1.1 to 7.0.0 ([#416](https://github.com/fvaleye/tracarbon/issues/416))
* build(deps-dev): Bump ruff from 0.9.7 to 0.9.9 ([#419](https://github.com/fvaleye/tracarbon/issues/419))
* build(deps): Bump typer from 0.15.1 to 0.15.2 ([#420](https://github.com/fvaleye/tracarbon/issues/420))
* build(deps-dev): Bump pytest from 8.3.4 to 8.3.5 ([#421](https://github.com/fvaleye/tracarbon/issues/421))
* build(deps-dev): Bump ruff from 0.9.10 to 0.11.13 ([#428](https://github.com/fvaleye/tracarbon/issues/428))
* build(deps-dev): Bump sphinx from 7.1.2 to 7.4.7 ([#427](https://github.com/fvaleye/tracarbon/issues/427))
* build(deps): Bump python-dotenv from 1.0.1 to 1.1.0 ([#426](https://github.com/fvaleye/tracarbon/issues/426))
* build(deps): Bump kubernetes from 31.0.0 to 33.1.0 ([#429](https://github.com/fvaleye/tracarbon/issues/429))
* build(deps): Bump typer from 0.15.4 to 0.16.0 ([#433](https://github.com/fvaleye/tracarbon/issues/433))
* build(deps-dev): Bump types-ujson from 5.10.0.20240515 to 5.10.0.20250326 ([#425](https://github.com/fvaleye/tracarbon/issues/425))
* build(deps): Bump ec2-metadata from 2.13.0 to 2.14.0 ([#432](https://github.com/fvaleye/tracarbon/issues/432))
* build(deps-dev): Bump types-requests from 2.32.0.20241016 to 2.32.4.20250611 ([#431](https://github.com/fvaleye/tracarbon/issues/431))
* build(deps): Bump msgpack from 1.1.0 to 1.1.1 ([#437](https://github.com/fvaleye/tracarbon/issues/437))


## [0.7.5](https://github.com/fvaleye/tracarbon/compare/v0.7.4...v0.7.5) (2025-06-03)


### Bug Fixes

* metrics appear when launching with the CLI ([#423](https://github.com/fvaleye/tracarbon/issues/423))


### Dependencies

* build(deps-dev): Bump ruff from 0.8.5 to 0.8.6 ([#405](https://github.com/fvaleye/tracarbon/issues/405))
* build(deps): Bump pydantic from 1.10.19 to 1.10.21 ([#409](https://github.com/fvaleye/tracarbon/issues/409))
* build(deps-dev): Bump ruff from 0.8.6 to 0.9.3 ([#411](https://github.com/fvaleye/tracarbon/issues/411))
* build(deps-dev): Bump ruff from 0.9.3 to 0.9.5 ([#414](https://github.com/fvaleye/tracarbon/issues/414))
* build(deps): Bump datadog from 0.50.2 to 0.51.0 ([#412](https://github.com/fvaleye/tracarbon/issues/412))
* build(deps-dev): Bump ruff from 0.9.5 to 0.9.7 ([#418](https://github.com/fvaleye/tracarbon/issues/418))
* build(deps): Bump psutil from 6.1.1 to 7.0.0 ([#416](https://github.com/fvaleye/tracarbon/issues/416))
* build(deps-dev): Bump ruff from 0.9.7 to 0.9.9 ([#419](https://github.com/fvaleye/tracarbon/issues/419))
* build(deps): Bump typer from 0.15.1 to 0.15.2 ([#420](https://github.com/fvaleye/tracarbon/issues/420))


## [0.7.4](https://github.com/fvaleye/tracarbon/compare/v0.7.3...v0.7.4) (2025-01-03)


### Changes

* Add support for multiple packages for RAPL sensor ([#392](https://github.com/fvaleye/tracarbon/issues/392))
* Update Mac sensor with the latest version of ioreg ([#402](https://github.com/fvaleye/tracarbon/issues/402))


### Dependencies

* build(deps): Bump aiohttp from 3.10.10 to 3.10.11 ([#387](https://github.com/fvaleye/tracarbon/issues/387))
* build(deps): Bump prometheus-client from 0.20.0 to 0.21.0 ([#385](https://github.com/fvaleye/tracarbon/issues/385))
* build(deps-dev): Bump ruff from 0.7.3 to 0.7.4 ([#386](https://github.com/fvaleye/tracarbon/issues/386))
* build(deps): Bump datadog from 0.50.1 to 0.50.2 ([#390](https://github.com/fvaleye/tracarbon/issues/390))
* build(deps): Bump asyncer from 0.0.7 to 0.0.8 ([#383](https://github.com/fvaleye/tracarbon/issues/383))
* build(deps): Bump typer from 0.12.5 to 0.15.1 ([#396](https://github.com/fvaleye/tracarbon/issues/396))


## [0.7.3](https://github.com/fvaleye/tracarbon/compare/v0.7.2...v0.7.3) (2024-11-13)


### Changes

* chore(dependencies): update the dependencies with latest updates ([#348](https://github.com/fvaleye/tracarbon/issues/348))
* chore(dependencies): update the dependencies 11-2024 ([#381](https://github.com/fvaleye/tracarbon/issues/381))


### Dependencies

* build(deps): Bump typer from 0.9.0 to 0.10.0 ([#302](https://github.com/fvaleye/tracarbon/issues/302))
* build(deps-dev): Bump ruff from 0.3.3 to 0.3.4 ([#303](https://github.com/fvaleye/tracarbon/issues/303))
* build(deps-dev): Bump pytest-mock from 3.12.0 to 3.14.0 ([#301](https://github.com/fvaleye/tracarbon/issues/301))
* build(deps-dev): Bump types-requests from 2.31.0.20240311 to 2.31.0.20240406 ([#310](https://github.com/fvaleye/tracarbon/issues/310))
* build(deps-dev): Bump types-aiofiles from 23.2.0.20240311 to 23.2.0.20240403 ([#308](https://github.com/fvaleye/tracarbon/issues/308))
* build(deps-dev): Bump pytest-cov from 4.1.0 to 5.0.0 ([#304](https://github.com/fvaleye/tracarbon/issues/304))
* build(deps): Bump pydantic from 1.10.14 to 1.10.15 ([#315](https://github.com/fvaleye/tracarbon/issues/315))
* build(deps-dev): Bump ruff from 0.3.4 to 0.3.7 ([#312](https://github.com/fvaleye/tracarbon/issues/312))
* build(deps): Bump aiohttp from 3.9.3 to 3.9.4 ([#314](https://github.com/fvaleye/tracarbon/issues/314))
* build(deps): Bump typer from 0.10.0 to 0.12.3 ([#313](https://github.com/fvaleye/tracarbon/issues/313))
* build(deps-dev): Bump autodoc-pydantic from 1.9.0 to 1.9.1 ([#318](https://github.com/fvaleye/tracarbon/issues/318))
* build(deps): Bump aiohttp from 3.9.4 to 3.9.5 ([#317](https://github.com/fvaleye/tracarbon/issues/317))
* build(deps-dev): Bump ruff from 0.3.7 to 0.4.1 ([#316](https://github.com/fvaleye/tracarbon/issues/316))
* build(deps): Bump datadog from 0.48.0 to 0.49.1 ([#306](https://github.com/fvaleye/tracarbon/issues/306))
* build(deps-dev): Bump pytest-xdist from 3.5.0 to 3.6.1 ([#320](https://github.com/fvaleye/tracarbon/issues/320))
* build(deps-dev): Bump pytest from 8.1.1 to 8.2.0 ([#321](https://github.com/fvaleye/tracarbon/issues/321))
* build(deps-dev): Bump ruff from 0.4.1 to 0.4.4 ([#325](https://github.com/fvaleye/tracarbon/issues/325))
* build(deps): Bump asyncer from 0.0.5 to 0.0.7 ([#324](https://github.com/fvaleye/tracarbon/issues/324))
* build(deps-dev): Bump mypy from 1.9.0 to 1.10.0 ([#322](https://github.com/fvaleye/tracarbon/issues/322))
* build(deps-dev): Bump pytest from 8.2.0 to 8.2.1 ([#329](https://github.com/fvaleye/tracarbon/issues/329))
* build(deps): Bump ujson from 5.9.0 to 5.10.0 ([#326](https://github.com/fvaleye/tracarbon/issues/326))
* build(deps-dev): Bump types-ujson from 5.9.0.0 to 5.10.0.20240515 ([#327](https://github.com/fvaleye/tracarbon/issues/327))
* build(deps-dev): Bump pytest-asyncio from 0.23.6 to 0.23.7 ([#328](https://github.com/fvaleye/tracarbon/issues/328))
* build(deps-dev): Bump bandit from 1.7.8 to 1.7.9 ([#338](https://github.com/fvaleye/tracarbon/issues/338))
* build(deps-dev): Bump ruff from 0.4.4 to 0.5.1 ([#343](https://github.com/fvaleye/tracarbon/issues/343))
* build(deps-dev): Bump types-aiofiles from 23.2.0.20240403 to 24.1.0.20240626 ([#345](https://github.com/fvaleye/tracarbon/issues/345))
* build(deps): Bump kubernetes from 29.0.0 to 30.1.0 ([#336](https://github.com/fvaleye/tracarbon/issues/336))
* build(deps): Bump psutil from 5.9.8 to 6.0.0 ([#352](https://github.com/fvaleye/tracarbon/issues/352))
* build(deps-dev): Bump ruff from 0.5.5 to 0.5.6 ([#351](https://github.com/fvaleye/tracarbon/issues/351))
* build(deps): Bump aiohttp from 3.10.0 to 3.10.1 ([#349](https://github.com/fvaleye/tracarbon/issues/349))
* build(deps): Bump aiofiles from 23.2.1 to 24.1.0 ([#350](https://github.com/fvaleye/tracarbon/issues/350))
* build(deps-dev): Bump ruff from 0.5.6 to 0.6.5 ([#365](https://github.com/fvaleye/tracarbon/issues/365))
* build(deps): Bump aiohttp from 3.10.1 to 3.10.5 ([#359](https://github.com/fvaleye/tracarbon/issues/359))
* build(deps-dev): Bump ruff from 0.6.5 to 0.6.8 ([#369](https://github.com/fvaleye/tracarbon/issues/369))
* build(deps): Bump datadog from 0.49.1 to 0.50.1 ([#368](https://github.com/fvaleye/tracarbon/issues/368))
* build(deps): Bump aiohttp from 3.10.5 to 3.10.9 ([#371](https://github.com/fvaleye/tracarbon/issues/371))
* build(deps): Bump typer from 0.12.3 to 0.12.5 ([#358](https://github.com/fvaleye/tracarbon/issues/358))
* build(deps): Bump pydantic from 1.10.17 to 1.10.18 ([#370](https://github.com/fvaleye/tracarbon/issues/370))
* build(deps): Bump kubernetes from 30.1.0 to 31.0.0 ([#366](https://github.com/fvaleye/tracarbon/issues/366))
* build(deps): Bump aiohttp from 3.10.9 to 3.10.10 ([#374](https://github.com/fvaleye/tracarbon/issues/374))
* build(deps-dev): Bump ruff from 0.6.8 to 0.7.3 ([#380](https://github.com/fvaleye/tracarbon/issues/380))
* build(deps-dev): Bump pytest-asyncio from 0.23.8 to 0.24.0 ([#362](https://github.com/fvaleye/tracarbon/issues/362))


## [0.7.2](https://github.com/fvaleye/tracarbon/compare/v0.7.1...v0.7.2) (2024-03-21)


### Features

* **aws:** catch exceptions from ec2 library when running on cloud providers ([#299](https://github.com/fvaleye/tracarbon/issues/299))


### Bug Fixes

* **dependencies:** fix dependencies CI issues ([#292](https://github.com/fvaleye/tracarbon/issues/292))


### Changes

* Bump release to 0.7.2 ([#300](https://github.com/fvaleye/tracarbon/issues/300))


### Dependencies

* Bump types-ujson from 5.8.0.0 to 5.8.0.1 ([#215](https://github.com/fvaleye/tracarbon/issues/215))
* Bump aiohttp from 3.8.4 to 3.8.5 ([#213](https://github.com/fvaleye/tracarbon/issues/213))
* Bump types-aiofiles from 23.1.0.4 to 23.1.0.5 ([#212](https://github.com/fvaleye/tracarbon/issues/212))
* Bump types-requests from 2.31.0.1 to 2.31.0.2 ([#211](https://github.com/fvaleye/tracarbon/issues/211))
* Bump kubernetes from 26.1.0 to 27.2.0 ([#214](https://github.com/fvaleye/tracarbon/issues/214))
* Bump pydantic from 1.10.11 to 1.10.12 ([#216](https://github.com/fvaleye/tracarbon/issues/216))
* Bump sphinx from 7.0.1 to 7.1.1 ([#217](https://github.com/fvaleye/tracarbon/issues/217))
* Bump aiocache from 0.12.1 to 0.12.2 ([#219](https://github.com/fvaleye/tracarbon/issues/219))
* Bump sphinx from 7.1.1 to 7.1.2 ([#218](https://github.com/fvaleye/tracarbon/issues/218))
* Bump mypy from 1.4.1 to 1.5.0 ([#221](https://github.com/fvaleye/tracarbon/issues/221))
* Bump aiofiles from 23.1.0 to 23.2.1 ([#220](https://github.com/fvaleye/tracarbon/issues/220))
* Bump types-aiofiles from 23.1.0.5 to 23.2.0.0 ([#223](https://github.com/fvaleye/tracarbon/issues/223))
* Bump mypy from 1.5.0 to 1.5.1 ([#222](https://github.com/fvaleye/tracarbon/issues/222))
* Bump pytest from 7.4.0 to 7.4.1 ([#224](https://github.com/fvaleye/tracarbon/issues/224))
* Bump pytest from 7.4.1 to 7.4.2 ([#228](https://github.com/fvaleye/tracarbon/issues/228))
* Bump loguru from 0.7.0 to 0.7.1 ([#227](https://github.com/fvaleye/tracarbon/issues/227))
* Bump black from 23.7.0 to 23.9.1 ([#226](https://github.com/fvaleye/tracarbon/issues/226))
* Bump datadog from 0.46.0 to 0.47.0 ([#225](https://github.com/fvaleye/tracarbon/issues/225))
* Bump loguru from 0.7.1 to 0.7.2 ([#229](https://github.com/fvaleye/tracarbon/issues/229))
* Bump pydata-sphinx-theme from 0.13.3 to 0.14.0 ([#230](https://github.com/fvaleye/tracarbon/issues/230))
* Bump msgpack from 1.0.5 to 1.0.6 ([#234](https://github.com/fvaleye/tracarbon/issues/234))
* Bump kubernetes from 27.2.0 to 28.1.0 ([#233](https://github.com/fvaleye/tracarbon/issues/233))
* Bump types-requests from 2.31.0.2 to 2.31.0.4 ([#232](https://github.com/fvaleye/tracarbon/issues/232))
* Bump pydata-sphinx-theme from 0.14.0 to 0.14.1 ([#231](https://github.com/fvaleye/tracarbon/issues/231))
* Bump msgpack from 1.0.6 to 1.0.7 ([#237](https://github.com/fvaleye/tracarbon/issues/237))
* Bump aiohttp from 3.8.5 to 3.8.6 ([#238](https://github.com/fvaleye/tracarbon/issues/238))
* Bump types-requests from 2.31.0.4 to 2.31.0.6 ([#235](https://github.com/fvaleye/tracarbon/issues/235))
* Bump pydantic from 1.10.12 to 1.10.13 ([#236](https://github.com/fvaleye/tracarbon/issues/236))
* Bump psutil from 5.9.5 to 5.9.6 ([#240](https://github.com/fvaleye/tracarbon/issues/240))
* Bump mypy from 1.5.1 to 1.6.0 ([#239](https://github.com/fvaleye/tracarbon/issues/239))
* Bump mypy from 1.6.0 to 1.6.1 ([#244](https://github.com/fvaleye/tracarbon/issues/244))
* Bump pytest-mock from 3.11.1 to 3.12.0 ([#242](https://github.com/fvaleye/tracarbon/issues/242))
* Bump black from 23.9.1 to 23.10.0 ([#243](https://github.com/fvaleye/tracarbon/issues/243))
* Bump pytest from 7.4.2 to 7.4.3 ([#245](https://github.com/fvaleye/tracarbon/issues/245))
* Bump black from 23.10.0 to 23.10.1 ([#246](https://github.com/fvaleye/tracarbon/issues/246))
* Bump prometheus-client from 0.17.1 to 0.18.0 ([#249](https://github.com/fvaleye/tracarbon/issues/249))
* Bump pydata-sphinx-theme from 0.14.1 to 0.14.3 ([#248](https://github.com/fvaleye/tracarbon/issues/248))
* Bump pytest-xdist from 3.3.1 to 3.4.0 ([#250](https://github.com/fvaleye/tracarbon/issues/250))
* Bump black from 23.10.1 to 23.11.0 ([#252](https://github.com/fvaleye/tracarbon/issues/252))
* Bump mypy from 1.6.1 to 1.7.0 ([#251](https://github.com/fvaleye/tracarbon/issues/251))
* Bump aiohttp from 3.8.6 to 3.9.0 ([#253](https://github.com/fvaleye/tracarbon/issues/253))
* Bump prometheus-client from 0.18.0 to 0.19.0 ([#258](https://github.com/fvaleye/tracarbon/issues/258))
* Bump aiohttp from 3.9.0 to 3.9.1 ([#255](https://github.com/fvaleye/tracarbon/issues/255))
* Bump mypy from 1.7.0 to 1.7.1 ([#254](https://github.com/fvaleye/tracarbon/issues/254))
* Bump pydata-sphinx-theme from 0.14.3 to 0.14.4 ([#256](https://github.com/fvaleye/tracarbon/issues/256))
* Bump pytest-xdist from 3.4.0 to 3.5.0 ([#257](https://github.com/fvaleye/tracarbon/issues/257))
* Bump pytest-asyncio from 0.21.1 to 0.23.2 ([#259](https://github.com/fvaleye/tracarbon/issues/259))
* Bump isort from 5.12.0 to 5.13.0 ([#262](https://github.com/fvaleye/tracarbon/issues/262))
* Bump bandit from 1.7.5 to 1.7.6 ([#261](https://github.com/fvaleye/tracarbon/issues/261))
* Bump ujson from 5.8.0 to 5.9.0 ([#260](https://github.com/fvaleye/tracarbon/issues/260))
* Bump psutil from 5.9.6 to 5.9.7 ([#266](https://github.com/fvaleye/tracarbon/issues/266))
* Bump types-ujson from 5.8.0.1 to 5.9.0.0 ([#264](https://github.com/fvaleye/tracarbon/issues/264))
* Bump black from 23.11.0 to 23.12.0 ([#265](https://github.com/fvaleye/tracarbon/issues/265))
* Bump isort from 5.13.0 to 5.13.2 ([#263](https://github.com/fvaleye/tracarbon/issues/263))
* Bump pytest from 7.4.3 to 7.4.4 ([#269](https://github.com/fvaleye/tracarbon/issues/269))
* Bump black from 23.12.0 to 23.12.1 ([#268](https://github.com/fvaleye/tracarbon/issues/268))
* Bump types-aiofiles from 23.2.0.0 to 23.2.0.20240106 ([#271](https://github.com/fvaleye/tracarbon/issues/271))
* Bump pytest-asyncio from 0.23.2 to 0.23.3 ([#270](https://github.com/fvaleye/tracarbon/issues/270))
* Bump mypy from 1.7.1 to 1.8.0 ([#267](https://github.com/fvaleye/tracarbon/issues/267))
* Bump kubernetes from 28.1.0 to 29.0.0 ([#272](https://github.com/fvaleye/tracarbon/issues/272))
* Bump types-requests from 2.31.0.6 to 2.31.0.20240106 ([#276](https://github.com/fvaleye/tracarbon/issues/276))
* Bump datadog from 0.47.0 to 0.48.0 ([#275](https://github.com/fvaleye/tracarbon/issues/275))
* Bump pydantic from 1.10.13 to 1.10.14 ([#274](https://github.com/fvaleye/tracarbon/issues/274))
* Bump bandit from 1.7.6 to 1.7.7 ([#280](https://github.com/fvaleye/tracarbon/issues/280))
* Bump python-dotenv from 1.0.0 to 1.0.1 ([#279](https://github.com/fvaleye/tracarbon/issues/279))
* Bump pytest-asyncio from 0.23.3 to 0.23.4 ([#278](https://github.com/fvaleye/tracarbon/issues/278))
* Bump asyncer from 0.0.2 to 0.0.4 ([#277](https://github.com/fvaleye/tracarbon/issues/277))
* Bump psutil from 5.9.7 to 5.9.8 ([#273](https://github.com/fvaleye/tracarbon/issues/273))
* Bump aiohttp from 3.9.1 to 3.9.3 ([#283](https://github.com/fvaleye/tracarbon/issues/283))
* Bump types-requests from 2.31.0.20240106 to 2.31.0.20240125 ([#281](https://github.com/fvaleye/tracarbon/issues/281))
* Bump pytest-asyncio from 0.23.4 to 0.23.5 ([#284](https://github.com/fvaleye/tracarbon/issues/284))
* build(deps-dev): Bump types-requests from 2.31.0.20240125 to 2.31.0.20240218 ([#287](https://github.com/fvaleye/tracarbon/issues/287))
* build(deps): Bump prometheus-client from 0.19.0 to 0.20.0 ([#286](https://github.com/fvaleye/tracarbon/issues/286))
* build(deps): Bump msgpack from 1.0.7 to 1.0.8 ([#291](https://github.com/fvaleye/tracarbon/issues/291))


## [0.7.1](https://github.com/fvaleye/tracarbon/compare/v0.7.0...v0.7.1) (2023-07-17)


### Changes

* Improve Tracarbon report with average interval in seconds for each metric ([#208](https://github.com/fvaleye/tracarbon/issues/208))
* Bump release to 0.7.1 ([#210](https://github.com/fvaleye/tracarbon/issues/210))


### Dependencies

* Bump datadog from 0.45.0 to 0.46.0 ([#209](https://github.com/fvaleye/tracarbon/issues/209))


## [0.7.0](https://github.com/fvaleye/tracarbon/compare/v0.6.5...v0.7.0) (2023-07-15)


### Changes

* Change cloud carbon footprint repository for AWS carbon emissions ([#199](https://github.com/fvaleye/tracarbon/issues/199))
* Add rapl_available in helm to launch tracarbon on cloud providers ([#205](https://github.com/fvaleye/tracarbon/issues/205))
* Add Tracarbon Report to store running statistics ([#206](https://github.com/fvaleye/tracarbon/issues/206))
* Bump release to v0.7.0 ([#207](https://github.com/fvaleye/tracarbon/issues/207))


### Dependencies

* Bump pytest from 7.3.1 to 7.3.2 ([#196](https://github.com/fvaleye/tracarbon/issues/196))
* Bump ujson from 5.7.0 to 5.8.0 ([#193](https://github.com/fvaleye/tracarbon/issues/193))
* Bump pydantic from 1.10.8 to 1.10.9 ([#194](https://github.com/fvaleye/tracarbon/issues/194))
* Bump types-aiofiles from 23.1.0.3 to 23.1.0.4 ([#195](https://github.com/fvaleye/tracarbon/issues/195))
* Bump types-ujson from 5.7.0.5 to 5.8.0.0 ([#192](https://github.com/fvaleye/tracarbon/issues/192))
* Bump pytest-mock from 3.10.0 to 3.11.1 ([#198](https://github.com/fvaleye/tracarbon/issues/198))
* Bump ec2-metadata from 2.11.0 to 2.12.0 ([#197](https://github.com/fvaleye/tracarbon/issues/197))
* Bump pydantic from 1.10.9 to 2.0 ([#200](https://github.com/fvaleye/tracarbon/issues/200))
* Bump pydantic from 2.0 to 2.0.2 ([#201](https://github.com/fvaleye/tracarbon/issues/201))


## [0.6.5](https://github.com/fvaleye/tracarbon/compare/v0.6.4...v0.6.5) (2023-06-07)


### Changes

* Remove unused attributes ([#190](https://github.com/fvaleye/tracarbon/issues/190))
* Bump release to 0.6.5 ([#191](https://github.com/fvaleye/tracarbon/issues/191))


### Dependencies

* Bump pytest from 7.2.2 to 7.3.0 ([#167](https://github.com/fvaleye/tracarbon/issues/167))
* Bump mypy from 1.1.1 to 1.2.0 ([#166](https://github.com/fvaleye/tracarbon/issues/166))
* Bump loguru from 0.6.0 to 0.7.0 ([#169](https://github.com/fvaleye/tracarbon/issues/169))
* Bump types-ujson from 5.7.0.1 to 5.7.0.3 ([#170](https://github.com/fvaleye/tracarbon/issues/170))
* Bump pytest from 7.3.0 to 7.3.1 ([#168](https://github.com/fvaleye/tracarbon/issues/168))
* Bump psutil from 5.9.4 to 5.9.5 ([#173](https://github.com/fvaleye/tracarbon/issues/173))
* Bump aiocache from 0.12.0 to 0.12.1 ([#172](https://github.com/fvaleye/tracarbon/issues/172))
* Bump sphinx from 6.1.3 to 6.2.0 ([#171](https://github.com/fvaleye/tracarbon/issues/171))
* Bump types-ujson from 5.7.0.3 to 5.7.0.4 ([#177](https://github.com/fvaleye/tracarbon/issues/177))
* Bump types-aiofiles from 23.1.0.1 to 23.1.0.2 ([#174](https://github.com/fvaleye/tracarbon/issues/174))
* Bump types-requests from 2.28.11.17 to 2.29.0.0 ([#175](https://github.com/fvaleye/tracarbon/issues/175))
* Bump sphinx from 6.2.0 to 7.0.0 ([#176](https://github.com/fvaleye/tracarbon/issues/176))
* Bump types-requests from 2.29.0.0 to 2.30.0.0 ([#180](https://github.com/fvaleye/tracarbon/issues/180))
* Bump types-ujson from 5.7.0.4 to 5.7.0.5 ([#178](https://github.com/fvaleye/tracarbon/issues/178))
* Bump typer from 0.7.0 to 0.9.0 ([#179](https://github.com/fvaleye/tracarbon/issues/179))
* Bump mypy from 1.2.0 to 1.3.0 ([#181](https://github.com/fvaleye/tracarbon/issues/181))
* Bump sphinx from 7.0.0 to 7.0.1 ([#182](https://github.com/fvaleye/tracarbon/issues/182))
* Bump pytest-xdist from 3.2.1 to 3.3.0 ([#183](https://github.com/fvaleye/tracarbon/issues/183))
* Bump pytest-xdist from 3.3.0 to 3.3.1 ([#184](https://github.com/fvaleye/tracarbon/issues/184))
* Bump pytest-cov from 4.0.0 to 4.1.0 ([#185](https://github.com/fvaleye/tracarbon/issues/185))
* Bump pydantic from 1.10.7 to 1.10.8 ([#188](https://github.com/fvaleye/tracarbon/issues/188))
* Bump types-aiofiles from 23.1.0.2 to 23.1.0.3 ([#186](https://github.com/fvaleye/tracarbon/issues/186))
* Bump prometheus-client from 0.16.0 to 0.17.0 ([#189](https://github.com/fvaleye/tracarbon/issues/189))
* Bump types-requests from 2.30.0.0 to 2.31.0.1 ([#187](https://github.com/fvaleye/tracarbon/issues/187))


## [0.6.4](https://github.com/fvaleye/tracarbon/compare/v0.6.3...v0.6.4) (2023-04-04)


### Changes

* Handle the exception when Tracarbon is failing to get the latest carbon factor of the location ([#164](https://github.com/fvaleye/tracarbon/issues/164))
* Bump release to v0.6.4 ([#165](https://github.com/fvaleye/tracarbon/issues/165))


### Dependencies

* Bump radon from 5.1.0 to 6.0.1 ([#157](https://github.com/fvaleye/tracarbon/issues/157))
* Bump pydantic from 1.10.6 to 1.10.7 ([#159](https://github.com/fvaleye/tracarbon/issues/159))
* Bump types-requests from 2.28.11.15 to 2.28.11.16 ([#158](https://github.com/fvaleye/tracarbon/issues/158))
* Bump types-requests from 2.28.11.16 to 2.28.11.17 ([#163](https://github.com/fvaleye/tracarbon/issues/163))
* Bump types-aiofiles from 23.1.0.0 to 23.1.0.1 ([#160](https://github.com/fvaleye/tracarbon/issues/160))
* Bump black from 23.1.0 to 23.3.0 ([#162](https://github.com/fvaleye/tracarbon/issues/162))
* Bump pydata-sphinx-theme from 0.13.1 to 0.13.3 ([#161](https://github.com/fvaleye/tracarbon/issues/161))


## [0.6.3](https://github.com/fvaleye/tracarbon/compare/v0.6.2...v0.6.3) (2023-03-22)


### Changes

* Avoid sending None metric value ([#156](https://github.com/fvaleye/tracarbon/issues/156))


## [0.6.2](https://github.com/fvaleye/tracarbon/compare/v0.6.1...v0.6.2) (2023-03-22)


### Changes

* Fix the country code for EU file when launching Tracarbon ([#155](https://github.com/fvaleye/tracarbon/issues/155))


## [0.6.1](https://github.com/fvaleye/tracarbon/compare/v0.6.0...v0.6.1) (2023-03-22)


### Changes

* Make country code in lowercase ([#154](https://github.com/fvaleye/tracarbon/issues/154))


### Dependencies

* Bump pytest-asyncio from 0.20.3 to 0.21.0 ([#149](https://github.com/fvaleye/tracarbon/issues/149))
* Bump datadog from 0.44.0 to 0.45.0 ([#150](https://github.com/fvaleye/tracarbon/issues/150))


## [0.6.0](https://github.com/fvaleye/tracarbon/compare/v0.5.5...v0.6.0) (2023-03-22)


### Changes

* Add the usage details in the energy consumption and carbon emissions generators ([#152](https://github.com/fvaleye/tracarbon/issues/152))
* Add the URL of the endpoint of the CO2 Signal API as a configuration key ([#151](https://github.com/fvaleye/tracarbon/issues/151))


### Dependencies

* Bump types-aiofiles from 22.1.0.9 to 23.1.0.0 ([#145](https://github.com/fvaleye/tracarbon/issues/145))


## [0.5.5](https://github.com/fvaleye/tracarbon/compare/v0.5.4...v0.5.5) (2023-03-13)


### Changes

* Add prefix name in Helm chart ([#147](https://github.com/fvaleye/tracarbon/issues/147))
* Bump release to 0.5.5 ([#148](https://github.com/fvaleye/tracarbon/issues/148))


### Dependencies

* Bump python-dotenv from 0.21.1 to 1.0.0 ([#146](https://github.com/fvaleye/tracarbon/issues/146))


## [0.5.4](https://github.com/fvaleye/tracarbon/compare/v0.5.3...v0.5.4) (2023-03-10)


### Changes

* Fix the RAPL negative values with Linux hardware again ([#142](https://github.com/fvaleye/tracarbon/issues/142))
* Bump release to v0.5.4 ([#143](https://github.com/fvaleye/tracarbon/issues/143))


## [0.5.3](https://github.com/fvaleye/tracarbon/compare/v0.5.2...v0.5.3) (2023-03-07)


### Changes

* Update dependencies and set Python to 3.8 ([#139](https://github.com/fvaleye/tracarbon/issues/139))
* Fix negative value with RAPL wrap-around for Linux hardware ([#140](https://github.com/fvaleye/tracarbon/issues/140))
* Bump release to v0.5.3 ([#141](https://github.com/fvaleye/tracarbon/issues/141))


### Dependencies

* Bump pytest from 7.2.1 to 7.2.2 ([#137](https://github.com/fvaleye/tracarbon/issues/137))


## [0.5.2](https://github.com/fvaleye/tracarbon/compare/v0.5.1...v0.5.2) (2023-03-03)


### Dependencies

* Bump prometheus-client from 0.15.0 to 0.16.0 ([#121](https://github.com/fvaleye/tracarbon/issues/121))
* Bump isort from 5.11.4 to 5.11.5 ([#123](https://github.com/fvaleye/tracarbon/issues/123))
* Bump black from 22.12.0 to 23.1.0 ([#122](https://github.com/fvaleye/tracarbon/issues/122))
* Bump mypy from 0.991 to 1.0.0 ([#126](https://github.com/fvaleye/tracarbon/issues/126))
* Bump aiofiles from 22.1.0 to 23.1.0 ([#125](https://github.com/fvaleye/tracarbon/issues/125))
* Bump aiohttp from 3.8.3 to 3.8.4 ([#124](https://github.com/fvaleye/tracarbon/issues/124))
* Bump mypy from 1.0.0 to 1.0.1 ([#127](https://github.com/fvaleye/tracarbon/issues/127))
* Bump pydantic from 1.10.4 to 1.10.5 ([#130](https://github.com/fvaleye/tracarbon/issues/130))
* Bump types-aiofiles from 22.1.0.7 to 22.1.0.8 ([#131](https://github.com/fvaleye/tracarbon/issues/131))
* Bump types-requests from 2.28.11.12 to 2.28.11.13 ([#129](https://github.com/fvaleye/tracarbon/issues/129))
* Bump kubernetes from 25.3.0 to 26.1.0 ([#128](https://github.com/fvaleye/tracarbon/issues/128))
* Bump types-ujson from 5.7.0.0 to 5.7.0.1 ([#134](https://github.com/fvaleye/tracarbon/issues/134))
* Bump types-aiofiles from 22.1.0.8 to 22.1.0.9 ([#133](https://github.com/fvaleye/tracarbon/issues/133))
* Bump types-requests from 2.28.11.13 to 2.28.11.15 ([#132](https://github.com/fvaleye/tracarbon/issues/132))


## [0.5.1](https://github.com/fvaleye/tracarbon/compare/v0.5.0...v0.5.1) (2023-01-24)


### Changes

* Improve the management of the optional dependencies ([#119](https://github.com/fvaleye/tracarbon/issues/119))


## [0.5.0](https://github.com/fvaleye/tracarbon/compare/v0.4.2...v0.5.0) (2023-01-24)


### Changes

* Improve README.md logo for PyPi ([#104](https://github.com/fvaleye/tracarbon/issues/104))
* Add MetricGenerator for the exporters. ([#111](https://github.com/fvaleye/tracarbon/issues/111))
* Add the RAPL domains in the Linux EnergyConsumption sensor ([#113](https://github.com/fvaleye/tracarbon/issues/113))
* Add Kubernetes generator for Energy Consumption and Carbon Emission ([#114](https://github.com/fvaleye/tracarbon/issues/114))


### Dependencies

* Bump isort from 5.11.2 to 5.11.3 ([#105](https://github.com/fvaleye/tracarbon/issues/105))
* Bump isort from 5.11.3 to 5.11.4 ([#106](https://github.com/fvaleye/tracarbon/issues/106))
* Bump types-requests from 2.28.11.5 to 2.28.11.7 ([#107](https://github.com/fvaleye/tracarbon/issues/107))
* Bump pydantic from 1.10.2 to 1.10.4 ([#108](https://github.com/fvaleye/tracarbon/issues/108))
* Bump types-ujson from 5.6.0.0 to 5.7.0.0 ([#110](https://github.com/fvaleye/tracarbon/issues/110))
* Bump ujson from 5.6.0 to 5.7.0 ([#109](https://github.com/fvaleye/tracarbon/issues/109))
* Bump aiocache from 0.11.1 to 0.12.0 ([#112](https://github.com/fvaleye/tracarbon/issues/112))


## [0.4.2](https://github.com/fvaleye/tracarbon/compare/v0.4.1...v0.4.2) (2022-12-14)


### Changes

* Update dependencies and Github actions ([#93](https://github.com/fvaleye/tracarbon/issues/93))
* Fix RAPL energy measurement when energy_uj is above max_energy_range_uj ([#97](https://github.com/fvaleye/tracarbon/issues/97))
* Add general metrics preconfigured with units ([#101](https://github.com/fvaleye/tracarbon/issues/101))
* Fix uses in the Github Action release workflow. ([#103](https://github.com/fvaleye/tracarbon/issues/103))


### Dependencies

* Bump pytest-xdist from 3.0.2 to 3.1.0 ([#96](https://github.com/fvaleye/tracarbon/issues/96))
* Bump ujson from 5.5.0 to 5.6.0 ([#95](https://github.com/fvaleye/tracarbon/issues/95))
* Bump types-ujson from 5.5.0 to 5.6.0.0 ([#94](https://github.com/fvaleye/tracarbon/issues/94))
* Bump ec2-metadata from 2.10.0 to 2.11.0 ([#99](https://github.com/fvaleye/tracarbon/issues/99))
* Bump black from 22.10.0 to 22.12.0 ([#98](https://github.com/fvaleye/tracarbon/issues/98))
* Bump pytest-asyncio from 0.20.2 to 0.20.3 ([#100](https://github.com/fvaleye/tracarbon/issues/100))


## [0.4.1](https://github.com/fvaleye/tracarbon/compare/v0.4.0...v0.4.1) (2022-11-22)


### Changes

* Fix the missing return statements for linux & windows ([#89](https://github.com/fvaleye/tracarbon/issues/89))


### Dependencies

* Bump typer from 0.6.1 to 0.7.0 ([#79](https://github.com/fvaleye/tracarbon/issues/79))
* Bump types-requests from 2.28.11.2 to 2.28.11.4 ([#80](https://github.com/fvaleye/tracarbon/issues/80))
* Bump psutil from 5.9.3 to 5.9.4 ([#83](https://github.com/fvaleye/tracarbon/issues/83))
* Bump types-aiofiles from 22.1.0.1 to 22.1.0.3 ([#81](https://github.com/fvaleye/tracarbon/issues/81))
* Bump pytest-asyncio from 0.20.1 to 0.20.2 ([#82](https://github.com/fvaleye/tracarbon/issues/82))
* Bump mypy from 0.982 to 0.990 ([#84](https://github.com/fvaleye/tracarbon/issues/84))
* Bump mypy from 0.990 to 0.991 ([#87](https://github.com/fvaleye/tracarbon/issues/87))
* Bump pydata-sphinx-theme from 0.11.0 to 0.12.0 ([#86](https://github.com/fvaleye/tracarbon/issues/86))
* Bump types-requests from 2.28.11.4 to 2.28.11.5 ([#85](https://github.com/fvaleye/tracarbon/issues/85))


## [0.4.0](https://github.com/fvaleye/tracarbon/compare/v0.3.2...v0.4.0) (2022-11-06)


### Changes

* Add RAPL energy measurements feature for the Linux Sensor ([#77](https://github.com/fvaleye/tracarbon/issues/77))


### Dependencies

* Bump prometheus-client from 0.14.1 to 0.15.0 ([#72](https://github.com/fvaleye/tracarbon/issues/72))
* Bump pydata-sphinx-theme from 0.10.1 to 0.11.0 ([#65](https://github.com/fvaleye/tracarbon/issues/65))
* Bump sphinx from 5.2.3 to 5.3.0 ([#71](https://github.com/fvaleye/tracarbon/issues/71))


## [0.3.2](https://github.com/fvaleye/tracarbon/compare/v0.3.1...v0.3.2) (2022-10-14)


### Changes

* Add JSONExporter in the exporters ([#61](https://github.com/fvaleye/tracarbon/issues/61))
* Add CODEOWNERS in Github ([#63](https://github.com/fvaleye/tracarbon/issues/63))
* Add Promotheus Exporter ([#69](https://github.com/fvaleye/tracarbon/issues/69))


### Dependencies

* Bump aiohttp from 3.8.1 to 3.8.3 ([#54](https://github.com/fvaleye/tracarbon/issues/54))
* Bump pytest-cov from 3.0.0 to 4.0.0 ([#60](https://github.com/fvaleye/tracarbon/issues/60))
* Bump mypy from 0.971 to 0.982 ([#64](https://github.com/fvaleye/tracarbon/issues/64))


## [0.3.1](https://github.com/fvaleye/tracarbon/compare/v0.3.0...v0.3.1) (2022-09-16)


### Changes

* Include CO2 Signal API to get the latest carbon intensity from different location ([#52](https://github.com/fvaleye/tracarbon/issues/52))


## [0.3.0](https://github.com/fvaleye/tracarbon/compare/v0.2.6...v0.3.0) (2022-09-16)


### Changes

* Include CO2 Signal API to get the latest carbon intensity from different location ([#51](https://github.com/fvaleye/tracarbon/issues/51))


## [0.2.6](https://github.com/fvaleye/tracarbon/compare/v0.2.5...v0.2.6) (2022-09-15)


### Changes

* Makefile follows gazr convention, add security and complexity actions ([#47](https://github.com/fvaleye/tracarbon/issues/47))
* Add the tracking of issues for devices ([#48](https://github.com/fvaleye/tracarbon/issues/48))
* Fix Github action when releasing the documentation ([#49](https://github.com/fvaleye/tracarbon/issues/49))


## [0.2.5](https://github.com/fvaleye/tracarbon/compare/v0.2.4...v0.2.5) (2022-09-14)


### Changes

* Add python-dotenv for development environment ([#44](https://github.com/fvaleye/tracarbon/issues/44))
* Add python-dotenv for development environment ([#44](https://github.com/fvaleye/tracarbon/issues/44))
* Add python-dotenv for development environment ([#44](https://github.com/fvaleye/tracarbon/issues/44))


### Dependencies

* Bump pydantic from 1.9.2 to 1.10.1 ([#37](https://github.com/fvaleye/tracarbon/issues/37))
* Bump psutil from 5.9.1 to 5.9.2 ([#38](https://github.com/fvaleye/tracarbon/issues/38))
* Bump black from 22.6.0 to 22.8.0 ([#40](https://github.com/fvaleye/tracarbon/issues/40))
* Bump pytest from 7.1.2 to 7.1.3 ([#39](https://github.com/fvaleye/tracarbon/issues/39))
* Bump pydata-sphinx-theme from 0.9.0 to 0.10.1 ([#41](https://github.com/fvaleye/tracarbon/issues/41))
* Bump types-requests from 2.28.9 to 2.28.10 ([#43](https://github.com/fvaleye/tracarbon/issues/43))
* Bump pydantic from 1.10.1 to 1.10.2 ([#42](https://github.com/fvaleye/tracarbon/issues/42))
* Bump pydantic from 1.9.2 to 1.10.1 ([#37](https://github.com/fvaleye/tracarbon/issues/37))
* Bump psutil from 5.9.1 to 5.9.2 ([#38](https://github.com/fvaleye/tracarbon/issues/38))
* Bump black from 22.6.0 to 22.8.0 ([#40](https://github.com/fvaleye/tracarbon/issues/40))
* Bump pytest from 7.1.2 to 7.1.3 ([#39](https://github.com/fvaleye/tracarbon/issues/39))
* Bump pydata-sphinx-theme from 0.9.0 to 0.10.1 ([#41](https://github.com/fvaleye/tracarbon/issues/41))
* Bump types-requests from 2.28.9 to 2.28.10 ([#43](https://github.com/fvaleye/tracarbon/issues/43))
* Bump pydantic from 1.10.1 to 1.10.2 ([#42](https://github.com/fvaleye/tracarbon/issues/42))
* Bump pydantic from 1.9.2 to 1.10.1 ([#37](https://github.com/fvaleye/tracarbon/issues/37))
* Bump psutil from 5.9.1 to 5.9.2 ([#38](https://github.com/fvaleye/tracarbon/issues/38))
* Bump black from 22.6.0 to 22.8.0 ([#40](https://github.com/fvaleye/tracarbon/issues/40))
* Bump pytest from 7.1.2 to 7.1.3 ([#39](https://github.com/fvaleye/tracarbon/issues/39))
* Bump pydata-sphinx-theme from 0.9.0 to 0.10.1 ([#41](https://github.com/fvaleye/tracarbon/issues/41))
* Bump types-requests from 2.28.9 to 2.28.10 ([#43](https://github.com/fvaleye/tracarbon/issues/43))
* Bump pydantic from 1.10.1 to 1.10.2 ([#42](https://github.com/fvaleye/tracarbon/issues/42))


## [0.2.4](https://github.com/fvaleye/tracarbon/compare/v0.2.3...v0.2.4) (2022-08-23)


### Changes

* Fix release documentation of the Github action ([#23](https://github.com/fvaleye/tracarbon/issues/23))


### Dependencies

* Bump types-ujson from 5.3.1 to 5.4.0 ([#24](https://github.com/fvaleye/tracarbon/issues/24))
* Bump typer from 0.4.2 to 0.5.0 ([#25](https://github.com/fvaleye/tracarbon/issues/25))
* Bump typer from 0.5.0 to 0.6.1 ([#26](https://github.com/fvaleye/tracarbon/issues/26))
* Bump types-requests from 2.28.0 to 2.28.1 ([#28](https://github.com/fvaleye/tracarbon/issues/28))
* Bump pytest-asyncio from 0.18.3 to 0.19.0 ([#27](https://github.com/fvaleye/tracarbon/issues/27))
* Bump mypy from 0.961 to 0.971 ([#30](https://github.com/fvaleye/tracarbon/issues/30))
* Bump types-requests from 2.28.1 to 2.28.3 ([#29](https://github.com/fvaleye/tracarbon/issues/29))
* Bump sphinx from 5.0.2 to 5.1.1 ([#31](https://github.com/fvaleye/tracarbon/issues/31))
* Bump types-requests from 2.28.3 to 2.28.6 ([#32](https://github.com/fvaleye/tracarbon/issues/32))
* Bump types-requests from 2.28.6 to 2.28.8 ([#33](https://github.com/fvaleye/tracarbon/issues/33))
* Bump pydantic from 1.9.1 to 1.9.2 ([#34](https://github.com/fvaleye/tracarbon/issues/34))
* Bump types-requests from 2.28.8 to 2.28.9 ([#35](https://github.com/fvaleye/tracarbon/issues/35))


## [0.2.3](https://github.com/fvaleye/tracarbon/compare/v0.2.2...v0.2.3) (2022-07-08)


### Changes

* Make easier the CLI usage of Tracarbon ([#7](https://github.com/fvaleye/tracarbon/issues/7))
* Add dependabot configuration and code of conduct ([#8](https://github.com/fvaleye/tracarbon/issues/8))
* Improve precision of the AWSEC2EnergyConsumption sensor and add GPU ([#17](https://github.com/fvaleye/tracarbon/issues/17))


### Dependencies

* Bump mypy from 0.950 to 0.961 ([#9](https://github.com/fvaleye/tracarbon/issues/9))
* Bump types-ujson from 4.2.1 to 5.2.0 ([#10](https://github.com/fvaleye/tracarbon/issues/10))
* Bump pydata-sphinx-theme from 0.8.1 to 0.9.0 ([#11](https://github.com/fvaleye/tracarbon/issues/11))
* Bump types-ujson from 5.2.0 to 5.3.0 ([#12](https://github.com/fvaleye/tracarbon/issues/12))
* Bump sphinx from 4.5.0 to 5.0.2 ([#13](https://github.com/fvaleye/tracarbon/issues/13))
* Bump requests from 2.15.1 to 2.20.0 ([#18](https://github.com/fvaleye/tracarbon/issues/18))
* Bump urllib3 from 1.24.3 to 1.26.5 ([#19](https://github.com/fvaleye/tracarbon/issues/19))
* Bump ujson from 5.3.0 to 5.4.0 ([#20](https://github.com/fvaleye/tracarbon/issues/20))
* Bump typer from 0.4.1 to 0.4.2 ([#21](https://github.com/fvaleye/tracarbon/issues/21))
* Bump black from 22.3.0 to 22.6.0 ([#22](https://github.com/fvaleye/tracarbon/issues/22))


## [0.2.2](https://github.com/fvaleye/tracarbon/compare/v0.2.1...v0.2.2) (2022-05-15)


### Changes

* Improve the docstring and update the dependencies ([#5](https://github.com/fvaleye/tracarbon/issues/5))


## [0.2.1](https://github.com/fvaleye/tracarbon/compare/v0.2.0...v0.2.1) (2022-05-15)


### Changes

* Improve the carbon emissions object. ([#3](https://github.com/fvaleye/tracarbon/issues/3))


## [0.2.0](https://github.com/fvaleye/tracarbon/compare/v0.1.0...v0.2.0) (2022-03-27)


### Changes

* Add a cloud providers interface calculating carbon emissions in a cloud provider environment
* Add the AWS EC2 service with energy consumption and carbon emissions calculators.


## 0.1.0 (2022-03-16)


### Changes

* Tracarbon's first version for measuring the energy consumption and calculating the carbon emissions of Mac devices and exports metrics on Stdout or Datadog.
