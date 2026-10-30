# Tracarbon

Use uv and the commands in [the development guide](docs/source/development.rst).
Run `make init` before checks and `make format` before committing. Run the relevant
pytest tests for code changes and `make build-documentation` for documentation changes.

## Architecture decisions

- Read the [decision index](docs/source/decisions/index.rst) and relevant accepted ADRs before changing a design.
- Add an ADR for significant changes to measurement semantics, public interfaces, or architecture. Routine fixes and refactors that preserve the design do not need one.
- Use the index's template and next unused number. Link evidence for the rationale, especially when documenting an earlier decision.
- Start proposals as `Proposed` and update their status after review. When replacing an accepted decision, mark it `Superseded`, link both records, and preserve the original rationale.
