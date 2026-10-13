## Summary
<!-- What changed and why. Link the Notion task if there is one. -->

## Tests performed
- [ ] `./start.sh --test` passes
- [ ] `./start.sh --mode demo --all` succeeds
- [ ] `uv run ruff check src tests` passes
- [ ] Real-data stage(s) run, if relevant: `./start.sh --mode real --steps ...`

## Dataset / schema impact
<!-- New or updated datasets (manifest updated?), changed canonical columns, CRS or units. -->
- [ ] No schema change, **or** `schemas.py` + `docs/data_contract.md` updated and reviewed
- [ ] New/updated raw data: `datasets.yaml` metadata filled, `--record-manifest` run

## Documentation
- [ ] README sections reviewed (status table, commands, team, plan) and updated if affected
- [ ] `CHANGELOG.md` updated under [Unreleased] — or reason it is not needed: ...
- [ ] Other docs updated if affected (methodology, assumptions, decisions, inventory)
- [ ] Notebook outputs cleared

## Review
Needs a second reviewer if it touches schemas, integration, CRS/spatial methods, scoring or
shared configuration.
