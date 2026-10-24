# Developing sensor definitions

Use Python 3.12 and Git; publication also needs GitHub CLI.

## Build and test

Install `requirements.txt`. Check out the exact commit in `sources/librenms.json` into `.upstream`, including all paths listed there and `LICENSE.txt`: OS discovery/detection definitions, the discovery include tree, OS classes and supporting device/interfaces directories. The build rejects incomplete checkouts. Never execute upstream discovery code.

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tools/catalogue.py build --upstream .upstream --version 1.0.0 --output artifacts/first
python tools/catalogue.py build --upstream .upstream --version 1.0.0 --output artifacts/second
```

Compare the generated files byte for byte. CI repeats this on Windows, macOS and Linux. Review `coverage.json` for unsupported/conflicting mappings. Add regression fixtures for mapping changes and preserve exact source paths and authoritative severity provenance.

Coverage includes an input inventory with per-source status, extracted mapping counts, omission reasons and content hashes. All discovery include/OS PHP files are accounted for, including files with no static state marker. A source with no static marker is not a claim that indirect state discovery is impossible. The legacy state PHP directory is always inventoried regardless of its contents or filename. Referenced sources missing from the inventory fail the build.

## Security checks

Install scanner tools separately from runtime requirements:

```text
python -m pip install -r requirements-security.txt
python tools/security_check.py
```

This audits both requirements files for known vulnerabilities, runs Bandit on `tools/` with a medium/high severity gate, and scans tracked files for potential secrets. Reports go to ignored `artifacts/security/`. CodeQL analyses Python and GitHub Actions on PRs, main pushes, weekly and manual runs.

Dependabot checks pinned requirements and action SHAs weekly. Review subprocess findings in context: invoke fixed Git/GitHub CLI executables with validated argument arrays, never a shell or upstream script. Keep publication contents-write permission scoped to jobs that need it; detection/validation use read-only permissions. Do not enable workflow PR review/approval permissions. Keep credentials and customer details out of logs, fixtures and commits. See [SECURITY.md](../SECURITY.md) for private reporting.

## Publish

The **Build LibreNMS releases** workflow detects the latest official stable release daily at 08:23 UTC or by manual dispatch. It resolves the tag to a commit, tests and builds twice on all three platforms, then publishes the matching version. The data tag retains its exact source lock. Feed activation is automatic, refuses downgrades/conflicting manifests and uses a normal fast-forward push. If activation fails after publication, the next run retries it. Versions are never overwritten.

The manual **Publish sensor definitions** workflow publishes separate catalogue versions from the current pinned input. Promote its released manifest to `feeds/v1/stable.json` through a reviewed PR after checks pass.

For a catalogue-only correction to LibreNMS 26.10.2, use `26.10.2+catalogue.1` and increase the correction number for later fixes. This keeps the upstream release identity and every published tag immutable, without reserving a future LibreNMS patch version. Readers must support correction versions before promoting one. Automated detection will not replace a correction with its uncorrected base release; a newer LibreNMS release still supersedes it.

Tags contain `data/manifest.json`, `data/os/<OS>.json.gz`, `data/coverage.json` and `data/notices.txt`. Only the manifest and notices are release attachments. Clients construct tagged raw GitHub URLs; unchanged OS content retains its hash across versions.

## Layout and standards

- `tools/`: importer, validation, release detection, publication and activation.
- `schemas/`: contracts; `examples/`: synthetic fixtures; `tests/`: regression tests.
- `sources/`: pinned input/provenance; `feeds/`: active index; `docs/`: design and development.
- `.upstream/`, `.deps/`, `artifacts/`: ignored local inputs, dependencies and output.

Follow [CONTRIBUTING.md](../CONTRIBUTING.md) and [CLAUDE.md](../CLAUDE.md): one issue per PR, squash-merge, `type(scope): lower-case user-visible result`, `Closes #NN` first in the PR body, no issue numbers or attribution in titles. Original code/documentation is MIT; derived data retains its upstream notices under [NOTICE.md](../NOTICE.md).
