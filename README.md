# DashyNMS sensor definitions — working draft

An independently updated catalogue of sensor state labels and severity mappings for DashyNMS Desktop, Mobile and MCP. Remote: [DashyNMS/sensor-definitions](https://github.com/DashyNMS/sensor-definitions), currently empty when this draft was prepared.

This folder is a local design draft which has not been pushed to that repository. It is not a production catalogue or implemented app feature. No app settings or network behaviour have changed.

## Agreed product requirements

- Users can turn sensor definitions on or off.
- Definitions are installation data, separate from server/account profiles. Keep downloaded definitions after sign-out and ordinary app upgrades.
- Turning the setting off stops resolution and updates, cancels outstanding downloads, and deletes all downloaded sensor definitions, including cached custom sources.
- Users can select the official repository or a custom compatible sensor definitions repository.
- Routine catalogue additions and corrections do not require an app release. Changes to the reader or supported schema can still require one.

## Proposed first version

Ship a small generated JSON catalogue, not the complete LibreNMS MIB collection or an SNMP runtime. Keep the updater and resolver in Core. Desktop supplies the settings UI and installation storage location; its bundled MCP process reads that same catalogue. Mobile integration follows using its platform's persistent installation data storage.

Prefer authoritative state translations supplied by the connected server when an API supports them. Otherwise use matching catalogue definitions. Unknown values and ambiguous matches remain unresolved; a label from a MIB alone does not establish alert severity.

Read [the design](docs/DESIGN.md), [delivery plan](docs/ROADMAP.md), and [contribution draft](CONTRIBUTING.md). The [catalogue schema](schemas/catalogue-v1.schema.json) and [synthetic example](examples/catalogue-v1.json) make the proposed data format reviewable. They are not the final release contract.

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

The generator and production release workflow are future work. The draft intentionally has no publishing automation.

## Source material

- [LibreNMS state sensor model](https://github.com/librenms/librenms/blob/master/app/Models/Sensor.php)
- [LibreNMS state support documentation](https://docs.librenms.org/Developing/Sensor-State-Support/)
- [Discovery definitions](https://github.com/librenms/librenms/tree/master/resources/definitions/os_discovery)
- [PHP state discovery](https://github.com/librenms/librenms/tree/master/includes/discovery/sensors/state)
- [MIBs](https://github.com/librenms/librenms/tree/master/mibs)

Research baseline: LibreNMS revision `fe6d56d3e6c55a0159ead8a5220e5fe51bd447a2`, inspected 23 October 2026. Its MIB tree totals 419,763,080 file-content bytes across 4,865 files. A production importer must pin and record its own input revision rather than follow a moving branch during a build.

Before publishing derived mappings, settle the repository's generator/data licensing and retain each upstream source's notices. Public availability is not a substitute for recording redistribution terms. No third-party mappings have been copied into the synthetic example.
