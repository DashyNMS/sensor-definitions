# DashyNMS sensor definitions

An independently updated catalogue of sensor state labels and severity mappings for DashyNMS Desktop, Mobile and MCP. The data is split by LibreNMS device OS so applications load only the systems they need.

The first importer supports static LibreNMS YAML state definitions and literal Cisco PHP state tables. It does not execute discovery code or redistribute the complete MIB collection. Dynamic or conflicting mappings are omitted and listed in the coverage report. MIB enum import and other PHP discovery families are future coverage work.

## Agreed product requirements

- Users can turn sensor definitions on or off.
- Definitions are installation data, separate from server/account profiles. Keep downloaded definitions after sign-out and ordinary app upgrades.
- Turning the setting off stops resolution and updates, cancels outstanding downloads, and deletes all downloaded sensor definitions, including cached custom sources.
- Users can select the official repository or a custom compatible sensor definitions repository.
- Routine catalogue additions and corrections do not require an app release. Changes to the reader or supported schema can still require one.

## Data format

Ship a small generated JSON catalogue, not the complete LibreNMS MIB collection or an SNMP runtime. Keep the updater and resolver in Core. Desktop supplies the settings UI and installation storage location; its bundled MCP process reads that same catalogue. Mobile integration follows using its platform's persistent installation data storage.

Prefer authoritative state translations supplied by the connected server when an API supports them. Otherwise use matching catalogue definitions. Unknown values and ambiguous matches remain unresolved; a label from a MIB alone does not establish alert severity.

Read [the design](docs/DESIGN.md), [delivery plan](docs/ROADMAP.md), and [contribution guide](CONTRIBUTING.md). The [index schema](schemas/index-v1.schema.json) describes the small stable feed; the [shard schema](schemas/catalogue-v1.schema.json) describes one OS's data. The [example](examples/catalogue-v1.json) is synthetic and is never published as vendor support.

`feeds/v1/stable.json` names the active catalogue version and each OS shard's hash and sizes. Data is fetched at `https://raw.githubusercontent.com/OWNER/REPO/vVERSION/data/os/OS.json.gz`. Shards contain no release number, so changing a catalogue release does not change the hash of an unchanged shard. Full source notices are in `data/notices.txt`, separately hash-checked and retained by the app.

Core keeps a bounded LRU of at most 16 OS shards / 4 MiB of source JSON. This bounds catalogue content retained in the lookup cache, not the process's total heap size. Parsed strings and lookup objects add overhead. Disk caches survive eviction from memory.

## Build and publish

Install Python 3.12 and `python -m pip install -r requirements.txt`. Check out the pinned revision from `sources/librenms.json` into `.upstream`, including the discovery/detection folders, state PHP folder and `LICENSE.txt`.

```text
python -m unittest discover -s tests -v
python tools/catalogue.py build --upstream .upstream --version 1.0.0 --output artifacts/release
```

CI runs the tests and two independent deterministic builds on Windows, macOS and Linux. The Publish sensor definitions workflow takes a stable version, validates/builds it, creates an immutable data tag and release, then proposes the stable feed change in a PR. The tag includes the generator source and data. Release attachments are just the manifest and notices; the hundreds of OS shards live under the immutable tag. Coverage/build reports remain Actions artifacts.

Merge the feed PR only after its checks pass. Apps receive that data update on their next enabled sync without an app release. Custom repositories can use the same workflow and contract. GitHub Actions needs permission to create PRs in the publishing repository.

## Repository layout

```text
docs/                 Architecture, update/storage policy and delivery plan
schemas/              Versioned JSON schemas
examples/             Synthetic examples, never promoted as real vendor support
sources/              Planned pinned upstream inputs and provenance records
definitions/          Planned normalised mappings and reviewed corrections
tools/                Planned importer, validator and deterministic packager
tests/                Planned matching, import and update fixtures
feeds/v1/stable.json   Planned stable release pointer for schema 1 readers
```

See [NOTICE.md](NOTICE.md) for the distinction between generator licensing and upstream-derived catalogue data.

## Source material

- [LibreNMS state sensor model](https://github.com/librenms/librenms/blob/master/app/Models/Sensor.php)
- [LibreNMS state support documentation](https://docs.librenms.org/Developing/Sensor-State-Support/)
- [Discovery definitions](https://github.com/librenms/librenms/tree/master/resources/definitions/os_discovery)
- [PHP state discovery](https://github.com/librenms/librenms/tree/master/includes/discovery/sensors/state)
- [MIBs](https://github.com/librenms/librenms/tree/master/mibs)

Research baseline: LibreNMS revision `fe6d56d3e6c55a0159ead8a5220e5fe51bd447a2`, inspected 23 October 2026. Its MIB tree totals 419,763,080 file-content bytes across 4,865 files. A production importer must pin and record its own input revision rather than follow a moving branch during a build.

The generator and original documentation are MIT-licensed. Generated LibreNMS mappings retain their source GPL-3.0-or-later notices, including the full upstream licence in each data release. No third-party mappings have been copied into the synthetic example.
