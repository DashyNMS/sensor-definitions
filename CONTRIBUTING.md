# Contributing

Match the DashyNMS repository conventions:

- Work on a branch; use one issue per PR into `main` and squash-merge.
- Commit and PR titles use `type(scope): lower-case user-visible result`, with no issue number or full stop. Suggested scopes: `definitions`, `import`, `schema`, `updates`, `docs`, `security`.
- PR descriptions begin with `Closes #NN`, describe the supported systems/change in behaviour, identify upstream revisions and summarise validation.
- No AI attribution or co-author lines in commits, PRs or release notes.
- Use British spelling and synthetic/documentation network identifiers.

Each mapping change must identify its source and include a fixture proving the numeric-to-label mapping and, separately, any generic severity mapping. Preserve upstream notices and distinguish vendor MIB enums from LibreNMS's interpretation. Do not submit customer hostnames, addresses, API responses, tokens or sign-in files.

CI validates schemas, duplicate or ambiguous selectors, state values, provenance and OIDs. Conflicting or unsupported discovery mappings are omitted and reported in coverage, not guessed. Run the importer tests and security checks in [the developer guide](docs/DEVELOPMENT.md) before opening a PR. Report vulnerabilities privately under [SECURITY.md](SECURITY.md).

Treat data releases as user-visible behaviour changes. Review label and severity corrections, publish immutable catalogue versions, and document changed coverage. A data repository must never ship instructions or scripts that client applications execute.

The approved upstream-release automation is the exception to manual feed PRs: an official stable LibreNMS release is pinned, validated on all three platforms, published under the matching version, and activated automatically. Changes to the importer, workflows and catalogue-specific corrections still follow the normal issue and PR review process. Do not overwrite published versions or force-push feed updates.
