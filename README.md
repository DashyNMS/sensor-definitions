<p align="center"><img src="https://dashynms.pckp.net/assets/img/favicon.svg" alt="" width="96" height="96"></p>
<h1 align="center">DashyNMS sensor definitions</h1>
<p align="center"><strong>Names and status colours for numeric sensor states.</strong><br>A shared catalogue that updates independently of the apps.</p>
<p align="center"><a href="https://dashynms.pckp.net/">Website</a> · <a href="https://github.com/DashyNMS/sensor-definitions/releases">Releases</a> · <a href="https://github.com/DashyNMS/sensor-definitions/issues">Issues</a></p>

---

DashyNMS sensor definitions translates numeric state readings into labels and status colours using LibreNMS mappings. [Core](https://github.com/DashyNMS/core) supplies the shared reader for Desktop and its bundled MCP server; Mobile integration follows separately.

## How it works

- **Download what you need:** a small index lists device operating systems. Each compressed OS file contains multiple mappings and downloads only when needed.
- **Keep raw readings:** labels supplement numeric values. Only authoritative generic states supply severity colours; unsupported values remain unresolved.
- **Choose the source:** use the official catalogue or a compatible custom repository. Selecting a source trusts its publisher; checksums detect corruption, not a compromised publisher.
- **Control the feature:** definitions are optional. Files survive sign-out; explicitly turning the setting off removes them.

The official pack imports definitions exclusively from LibreNMS. The importer supports literal YAML state tables, including implicit state names and fixed OID templates, and Cisco and Axis PHP discovery tables. Missing numeric OIDs can be resolved from official MIB files during generation. It never executes discovery code or redistributes the complete MIB collection. Unsupported, dynamic and conflicting mappings are reported rather than guessed. Not every sensor is supported yet; each data tag contains a coverage report.

## Updates and versions

The **Build LibreNMS releases** workflow checks the latest official stable release daily at 08:23 UTC. LibreNMS `26.10.2`, for example, produces catalogue `v26.10.2` from its exact commit. After tests and deterministic builds pass on Windows, macOS and Linux, publication and stable-feed activation happen automatically.

Detection can take a day plus GitHub scheduling delays. Enabled apps receive activated data on their next sync, normally within 24 hours, or through **Update sensor definitions**. No app rebuild is needed for routine catalogue changes. Reader/schema changes may need an app update.

Generated OS files live in release tags under `data/os/`, named by OS, such as `procurve.json.gz`. The `main` branch holds the generator and [active index](feeds/v1/stable.json). Release attachments contain the manifest and notices; OS files and coverage reports remain in the tag.

## Build and development

Use Python 3.12 and Git; publication also needs GitHub CLI.

```text
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The [developer guide](docs/DEVELOPMENT.md) covers pinned inputs, builds, security checks and publication. See [the design](docs/DESIGN.md), [schemas](schemas/) and [contribution guide](CONTRIBUTING.md) for the protocol and change standards.

Use one issue per PR into `main`, then squash-merge. Titles follow `type(scope): lower-case user-visible result`. Never commit customer network details or credentials.

## Help and feedback

- Bugs or missing mappings: [open an issue](https://github.com/DashyNMS/sensor-definitions/issues) with synthetic examples.
- Security problems: report privately using [SECURITY.md](SECURITY.md).

---

<sub>DashyNMS is not affiliated with LibreNMS or the vendors represented in the catalogue.<br>
Original generator code, schemas, tests and documentation use the MIT licence: see [LICENSE](LICENSE). LibreNMS-derived data retains its GPL-3.0-or-later terms and notices: see [NOTICE.md](NOTICE.md).</sub>
