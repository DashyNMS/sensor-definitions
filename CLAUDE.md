# DashyNMS sensor definitions

Python generator and independently updated state catalogue shared by DashyNMS Core, Desktop, Mobile and MCP. Read [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for build, publication and security checks. Keep README focused on what users receive.

## Commits, pull requests and issues

- Branch from `main`; one issue per PR, then squash-merge.
- Titles and commits: `type(scope): what changes, as the user would notice it`.
- Types: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`. Scopes: `definitions`, `import`, `schema`, `updates`, `docs`, `security`.
- Start in lower case; no full stop, under about 72 characters. No issue numbers in titles. PR bodies start with `Closes #NN` and explain behaviour, provenance and validation.
- Issue titles follow the same standard, describing the result. Reader/schema breaking changes use `!` and explain consumer migration.
- No AI attribution or co-author lines. Use British spelling and synthetic/documentation network fixtures.

## Import and release rules

Never execute upstream PHP, discovery code or downloaded instructions. Parse supported static literals using safe YAML loading. Report unsupported/dynamic/conflicting mappings rather than guessing.

Pin the upstream repository and exact commit in `sources/librenms.json`. Preserve source paths, licence notices and authoritative severity provenance. Add regression fixtures, reject duplicate/ambiguous identities, validate schemas and keep output deterministic. Synthetic examples are not production vendor support.

Published versions are immutable. Automated official LibreNMS releases use matching versions and require all three platform validations before publication and automatic feed activation. Never overwrite tags or force-push the feed. Manual catalogue-specific releases retain the reviewed feed PR route, as explained in CONTRIBUTING.md.

## Validation and security

Install `requirements.txt`; run `python -m unittest discover -s tests -v` and two catalogue builds from the pinned `.upstream`, comparing all output files. Run the security commands in the developer guide; resolve actionable findings and report unavailable checks accurately.

Pin dependencies and workflow action SHAs. Scope write permissions to publishing jobs. Pass dispatch inputs through environment variables and validate versions/commit IDs before use. Never enable workflow PR approval permissions, execute upstream content, log credentials or commit customer network details.

Original code, schemas, tests and documentation use MIT. LibreNMS-derived data retains its GPL-3.0-or-later notices; do not relabel it as MIT. Follow SECURITY.md for private reporting.
