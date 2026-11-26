# DashyNMS sensor definitions

Python generator and independently updated state catalogue shared by DashyNMS Core, Desktop, Mobile and MCP. Keep README focused on what users receive.

- Never execute upstream PHP, discovery code or downloaded instructions. Parse supported static literals using safe YAML loading. Report unsupported, dynamic or conflicting mappings rather than guessing.
- Pin the upstream repository and exact commit in `sources/librenms.json`. Preserve source paths, licence notices and authoritative severity provenance. Add regression fixtures, reject duplicate or ambiguous identities, validate schemas and keep output deterministic. Synthetic examples are not production vendor support.
- LibreNMS-derived data retains its GPL-3.0-or-later terms and notices. Keep it distinct from the MIT-licensed original code, schemas, tests and documentation.

## Repository conventions

- Before changing build, test or publication workflows, read [the developer guide](docs/DEVELOPMENT.md). Before changing release notes, read its [Release notes](docs/DEVELOPMENT.md#release-notes) section.
- Before changing shared conventions or security checks, read [Repository standards](docs/REPOSITORY-STANDARDS.md); update the canonical source and every affected consumer.
- Create or find an issue describing the bug or intended change before opening any PR, including dependency, documentation and CI changes. Every PR must reference its issue.
- Work on a branch; use one issue per PR into `main`, then squash-merge. The PR title becomes the commit subject on `main`.
- PR titles, branch commits and issue titles use `type(scope): what changes, as the user would notice it`. Read [Commits, pull requests and issues](docs/DEVELOPMENT.md#commits-pull-requests-and-issues) for this repository's types, scopes and examples.
- Start the description in lower case, omit the final full stop and aim for a complete subject under 72 characters. Separate two scopes with a comma; omit the scope when there is no single area. Document a new scope in the developer guide in the same PR.
- Word issue titles as the result the fixing PR delivers. Epics end with `(epic)`. Keep issue numbers out of titles; start the PR body with `Closes #NN` when resolving an issue, then explain what changes and how it was checked.
- Mark breaking changes with `!` and explain the migration and version implications for affected consumers.
- Dependabot uses `build(deps): ...` for every ecosystem. Its generated dependency names and grouped summaries may exceed the usual title length.
- Use British spelling in user-facing text. Keep real device names, hostnames, addresses, credentials and other identifiable network data out of issues, PRs, commits, logs, screenshots and fixtures. Use `example.net` and documentation address ranges.
- Commits, PRs and release notes carry no AI attribution or `Co-Authored-By` lines.
- Project-owned code, documentation and assets use the MIT licence in `LICENSE`. Preserve third-party licences, copyright notices and provenance; MIT does not replace upstream terms.

## Validation and releases

- Install `requirements.txt`; run `python -m unittest discover -s tests -v` and two catalogue builds from the pinned `.upstream`, comparing all output files. Run the developer guide's security checks; resolve actionable findings and report unavailable checks accurately.
- Pin dependencies and workflow action SHAs. Scope write permissions to publishing jobs. Pass dispatch inputs through environment variables and validate versions and commit IDs before use. Keep workflow PR approval permissions disabled. Follow [SECURITY.md](SECURITY.md) for private reporting.
- Published versions are immutable. Automated official LibreNMS releases use matching versions and require all three platform validations before publication and automatic feed activation. Never overwrite published tags or force-push the feed.
- Changes to the importer, workflows and manual catalogue-specific releases follow the reviewed PR route in [CONTRIBUTING.md](CONTRIBUTING.md). Approved upstream-release feed activation is the exception to manual PRs.
- A change people would notice adds or updates its line in `docs/releases/next.md` in the same PR. GitHub release notes come from that file and the generated catalogue summary.
