# Contribution and review draft

Match the DashyNMS repository conventions:

- Work on a branch; use one issue per PR into `main` and squash-merge.
- Commit and PR titles use `type(scope): lower-case user-visible result`, with no issue number or full stop. Suggested scopes: `definitions`, `import`, `schema`, `updates`, `docs`.
- PR descriptions begin with `Closes #NN`, describe the supported systems/change in behaviour, identify upstream revisions and summarise validation.
- No AI attribution or co-author lines in commits, PRs or release notes.
- Use British spelling and synthetic/documentation network identifiers.

Each mapping change must identify its source and include a fixture proving the numeric-to-label mapping and, separately, any generic severity mapping. Preserve upstream notices and distinguish vendor MIB enums from LibreNMS's interpretation. Do not submit customer hostnames, addresses, API responses, tokens or sign-in files.

The future CI validator should reject duplicate or ambiguous selectors, conflicting states, missing provenance, invalid OIDs and unsupported schema versions. Dynamic discovery that cannot be interpreted faithfully belongs in the coverage report, not a guessed generated record.

Treat data releases as user-visible behaviour changes. Review label and severity corrections, publish immutable catalogue versions, and document changed coverage. A data repository must never ship instructions or scripts that client applications execute.
