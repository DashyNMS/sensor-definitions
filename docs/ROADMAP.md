# Delivery plan draft

Keep each implementation issue in its own branch/commit/PR. Repository creation and publishing are separate from this local draft. No app build is required for writing this standalone proposal.

## 1. Repository foundation

The empty `DashyNMS/sensor-definitions` remote now exists. Review this local scaffold before making the first commit. Confirm visibility and licensing before publication; public catalogue downloads are the proposed first version. Establish `main`, review policy and the contributor conventions. Finalise schema 1, the feed format, publishing trust policy and the exact supported repository URL forms.

Acceptance: examples validate, unknown versions reject clearly, and malformed/duplicate data cannot be published. Keep synthetic fixtures out of release assets.

## 2. Small real catalogue

Start with several known state families, including at least one YAML mapping and one PHP discovery mapping. Build a pinned importer and coverage report, recording unsupported cases. Measure actual compressed size before expanding scope. Do not start by copying the entire MIB tree.

Acceptance: each label and generic state has source provenance and a fixture. Two systems using the same numeric value resolve independently. MIB-only labels never invent severity. Licence notices accompany derived data.

## 3. Core reader

Add typed sensor identity fields, conservative matching and unresolved results. Use a caller-supplied catalogue and storage path. Tests cover OID component boundaries, duplicate ambiguity, missing identity, missing and fractional values, label-only states, version incompatibility and concurrent reloads. All supported .NET target frameworks and operating systems must pass.

Acceptance: Desktop, Mobile and MCP can consume the same contract. Existing sensor display remains functional with the feature off or no catalogue available.

## 4. Installation store and updater

Implement the source adapters, source-separated cache, bounded downloads and atomic promotion. Finalise protected-install behaviour on Windows/macOS/Linux and validate the adjacent folder survives an ordinary upgrade. Desktop is the single writer for its bundled MCP reader.

Acceptance: sign-out preserves preference, source and data; explicit disable cancels downloads, clears memory and deletes only definition data; late writes cannot recreate it. Partial deletion is reported. Offline operation uses the selected source's validated cache. Custom-source changes never mix mappings or silently use another publisher.

## 5. Desktop settings and sensor display

Add Use sensor definitions, Official / Custom repository, repository entry, Update definitions and status. Persist these separately from account settings. Honour Apply and Apply & Save. Propagate changes to sensor lists, widgets, device details and the bundled MCP process without restarting.

Acceptance: on/off, source switching, failed downloads, failed cleanup, sign-out, re-sign-in and upgrades are exercised on all three desktop platforms. Mac data stays outside the signed app and Linux data stays outside the AppImage. Show the active source/version and the raw value when appropriate. Produce a dev build after each app commit as requested.

## 6. Data publishing and independent updates

Release immutable catalogue assets, then advance a schema-specific stable pointer. Prove an app can receive an added system definition without an app/Core/MCP binary update. Prove rollback to an explicitly selected known-good release and rejection of incompatible schema versions. Keep release assets limited to catalogue data and the agreed manifest/notices; diagnostic build records remain CI artifacts.

Only after these checks should the app's stable channel advertise remote catalogue updates. Do not run a Desktop preview release merely to publish new definitions.

## Decisions still open

- Confirm default off versus opt-in during first setup (off is the draft default).
- Final installation settings filenames and protected-install location remedy.
- Manifest signing and key/trust handling for official and custom sources.
- Generator/data licensing and upstream notices.
- First supported state families and the measured catalogue size budget.
- Compatibility selectors for mappings that vary by LibreNMS or device version.
- Private repositories and additional Git hosts after the public GitHub adapter.
- Mobile's persistent storage integration and independent MCP deployment ownership.
