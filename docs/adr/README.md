# Architecture decision records

An ADR records one significant decision: the context, the choice, and what follows from it.
Format: [MADR 4.0.0](https://github.com/adr/madr/tree/4.0.0) minimal, with a status line and a date.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-measure-linux-cpu-power-as-package-minus-uncore.md) | Measure Linux CPU power as the package minus the integrated GPU | Accepted |
| [0003](0003-attribute-cpu-energy-to-explicit-processes.md) | Attribute CPU energy to explicit processes | Accepted |
| [0004](0004-enforce-conventional-commits-and-automate-releases.md) | Enforce Conventional Commits and automate releases | Accepted |

## Adding an ADR

1. Copy [template.md](template.md) to `NNNN-title-with-dashes.md`, using the next number.
2. Fill it in, link the pull request, and add a row to the table above.
3. Never edit an accepted ADR's decision. Write a new ADR, set the old status to `Superseded by [ADR NNNN](NNNN-title.md)`, and update the table.

Write an ADR for a decision that future contributors would otherwise have to reverse engineer.
Skip it for bug fixes, workarounds, and anything the code or docs already explain.
