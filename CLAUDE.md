# Sensor definitions

Generated sensor state data consumed by Core, Desktop, Mobile and MCP. Never execute downloaded discovery code. Keep imports pinned, provenance intact and publication deterministic.

Work on a branch with one issue per PR into `main`, then squash-merge. Titles and commits use `type(scope): lower-case user-visible result`; suggested scopes are `definitions`, `import`, `schema`, `updates`, `docs`. PR bodies start with `Closes #NN`. No issue numbers in titles, AI attribution or co-author lines. Use British spelling and documentation-only network fixtures.

Run `python -m unittest discover -s tests -v` and `python tools/catalogue.py build --upstream .upstream --version 1.0.0 --output artifacts` after installing `requirements.txt`. The upstream revision must match `sources/librenms.json`. The build report must list unsupported imports rather than guess. A production build rejects synthetic sources.

Generator code is MIT; LibreNMS-derived data retains its GPL-3.0-or-later source notices. No customer identifiers or credentials belong here.
