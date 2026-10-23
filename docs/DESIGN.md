# Sensor definitions design draft

Status: proposal. The product requirements in the README reflect the user's instructions; defaults, paths and wire formats below remain implementation proposals.

## Ownership and settings

The definitions repository owns data generation, provenance, validation and catalogue releases. Core owns matching, catalogue parsing, download validation, caching and change notifications. The app owns user controls and supplies an absolute installation data directory. No UI framework belongs in the catalogue repository or Core reader.

Proposed Settings controls:

| Control | Behaviour |
| --- | --- |
| Use sensor definitions | Proposed default off; enabling permits lookup and synchronisation |
| Source | Official DashyNMS repository or Custom repository |
| Custom repository | HTTPS repository URL; first adapter supports public GitHub repositories |
| Update definitions | Manual check, available while enabled |
| Status | Selected source, active version, last successful sync, storage path and any error |

Changing a repository does not itself download while the feature is off. The settings flow must explain that disabling removes the downloaded definitions. Existing Apply / Apply & Save behaviour should apply these choices consistently.

Store this preference outside the account profile and outside the removable definitions directory. Sign-out must not reset the preference, chosen repository or cache. A proposed installation settings record contains `sensorDefinitions.enabled`, `sourceKind` and `customRepositoryUrl`; it contains no API tokens or account identifiers. Keep the custom repository choice when disabled so users can re-enable it without entering the URL again.

## Installation storage

The requirement is installation-local storage, not an account cache or the current working directory. Proposed locations:

| Platform | Proposed definitions directory |
| --- | --- |
| Windows per-user installer / extracted dev build | `<directory containing DashyNMS.exe>/sensor-definitions/` |
| macOS | `<directory containing DashyNMS.app>/DashyNMS.sensor-definitions/`, outside the signed app bundle |
| Linux AppImage | `<directory containing the AppImage>/DashyNMS.sensor-definitions/`, outside its mounted filesystem |

These paths need native validation before becoming the shipping contract. A Mac app bundle and an AppImage are not writable data folders. Their surrounding directories can also be protected. Do not request elevation or silently move the cache into a sign-out-cleared profile. If the installation directory is not writable, report that synchronisation is unavailable at that location and retain raw sensor readings. The supported remedy or explicit alternative installation-owned data path must be decided for protected installs before rollout.

An installation may retain several sources:

```text
<installation-data>/installation-settings.json
<definitions-root>/
  sources/<source-key>/manifest.json
  sources/<source-key>/catalogue.json
  staging/<unique-download>/...
```

`source-key` is derived from the canonical repository/feed identity, never a user-controlled filesystem path. Keep definitions free of server names, device identifiers, readings, sign-in tokens and chat history. The desktop passes the resolved directory and enabled state to its bundled MCP process; MCP must not derive its own cache under the `mcp` executable directory. Use one installation updater and read-only consumers with a shared resolver.

Ordinary sign-out, account switching and app upgrades leave this data alone. Updaters and uninstall tooling need explicit preservation rules for the adjacent folder and installation settings. Under the requested deletion policy, uninstall must not independently purge definitions: the user disables the feature to remove them. Mobile cannot modify its installed application package; its later integration needs persistent app-owned storage excluded from sign-out cleanup.

## Disabling and deletion

Disabling takes effect immediately for resolution and synchronisation. Cancel in-flight work, invalidate its generation token and wait for the writer lock before removing the definitions root, including all source caches, staged downloads and catalogue backups. Do not delete unrelated installation files or the installation settings record.

A completed download must recheck enabled state, selected source and generation while holding the commit lock. It must never recreate the folder after disable. Re-enabling starts a fresh sync. Failed deletion leaves the feature off and exposes a pending-cleanup error; do not report that files were removed when they remain.

Use path containment checks against the resolved installation definitions root for every deletion. Symlinks/reparse points must not redirect cleanup outside that root. Replacing an active catalogue during an update is normal synchronisation; wholesale cache removal is tied to explicit disable, not expiry, sign-out or an independent uninstall cleanup.

## Custom repositories

Accept a compatible catalogue repository, not an arbitrary MIB repository or executable importer. Initial scope is public HTTPS GitHub repository URLs such as `https://github.com/example-org/sensor-definitions`. Normalise owner/repository identity and reject malformed URLs, embedded credentials, query strings and traversal. Other Git hosts can use a future feed adapter with the same data contract. Private repository authentication is outside the first draft and must not reuse a LibreNMS API token.

Official and custom sources obey identical size, schema, provenance and integrity checks. A custom source is authoritative only when selected; do not silently merge it with official mappings. Switching source cancels obsolete updates and changes the generation token. Use a previously validated cache for the selected source, or raw readings while its first catalogue downloads. Keep other source caches until the feature is disabled. If the custom source fails, show the failure rather than quietly apply official definitions as if they came from the custom source.

Do not run code, PHP, shell scripts or MIB tooling downloaded from either source. Source import runs in the data repository's build process. Each catalogue release is independently versioned; end-user applications download the published data assets, not a Git checkout.

## Matching and interpretation

Version 1 matches state sensors using exact LibreNMS device `os`, exact sensor `sensor_type`, and a numeric OID prefix. All required selectors must be present and match. Normalise a leading dot on numeric OIDs; prefix comparison uses OID components, so `.1.2` cannot match `.1.20`. Match OS and sensor type as identifiers, not human-readable descriptions. Do not infer sensor identity from description text, IP addresses or vendor name alone.

Among candidates with the same exact identifiers, choose the longest matching OID prefix only if that leaves one definition. Equal-specificity conflicts are unresolved and fail catalogue validation when detectable. Never select whichever record happens to be first. Do not round a fractional reading to make it fit an enumeration. Integer values are encoded as canonical decimal strings in the catalogue to avoid JSON floating-point precision loss; Core only resolves values it can represent exactly from the API response.

Each resolved state has a label and an optional generic state: `ok`, `warning`, `critical` or `unknown`. `null` means no authoritative severity mapping is supplied, as can happen with a MIB-only enum. A label-only mapping must not turn an unknown state green or invent a threshold. These mappings describe sensor presentation; they do not create, recover or acknowledge LibreNMS alert records.

Resolution precedence:

1. A supported server API's explicit current state translation and generic state.
2. One verified catalogue match for the selected source and known compatible context.
3. Raw reading with unresolved state information.

Source revisions record provenance, not automatic compatibility with every LibreNMS release or device firmware. If mappings differ by server/firmware version and the first format cannot express that safely, omit that entry and report the coverage gap. Add an explicit compatibility selector in a reviewed schema revision before importing such variants. Unknown server compatibility must never be presented as verified compatibility.

## Import pipeline

Pin upstream repository and commit. Extract explicit state mappings from LibreNMS YAML where feasible; handle PHP discovery mappings with a constrained parser or reviewed extraction rather than executing upstream discovery. Supplement labels with MIB integer enums where an exact identity can be established. Preserve source paths, identifiers, notices and whether the severity is authoritative.

Emit deterministic ordering, detect duplicate selectors/values, and validate each mapping against fixtures. Do not turn unsupported dynamic discovery logic into a guessed mapping. Produce a coverage report listing imported, unsupported and conflicting definitions. Reviewed corrections need their own provenance and regression fixture. No real customer network data goes into fixtures.

The draft example uses the documentation-only enterprise number 32473: [RFC 5612](https://www.rfc-editor.org/rfc/rfc5612). It must not appear in a production vendor catalogue.

## Versioning and update protocol

Separate `schemaVersion` from `catalogueVersion`. A schema-1 reader follows `feeds/v1/stable.json`, even after schema 2 exists. Use immutable tagged releases for catalogue assets; publish the channel pointer only after its referenced release is available and validated. A stable feed must not select a prerelease catalogue.

Proposed stable pointer fields:

```json
{
  "schemaVersion": 1,
  "catalogueVersion": "1.0.0",
  "assetUrl": "https://github.com/OWNER/REPOSITORY/releases/download/v1.0.0/catalogue-v1.json.gz",
  "sha256": "<digest of the compressed asset>",
  "downloadBytes": 12345,
  "expandedBytes": 67890
}
```

This is illustrative, not a published feed. A feed schema and signing contract remain to be settled. HTTPS and SHA-256 bind the download to the selected publisher's manifest; a checksum alone does not authenticate a compromised publisher. Do not describe the first implementation as signed unless signing and verification actually exist. A signing policy, key ownership and custom-source trust model need review before automatic public rollout.

While enabled, proposed behaviour is one asynchronous check at startup if the last check was more than 24 hours ago, plus a manual update option. Repaint existing sensor values after an atomic catalogue swap; do not restart the app or discard selections. No update check should delay startup or require LibreNMS sign-in. Network failures keep the selected source's last validated catalogue.

Download to a fresh staging directory within the definitions root. Enforce HTTPS redirect/source policy, bounded sizes and decompression limits, checksum, supported schema and semantic validation before atomic promotion. Proposed initial limits: 8 MiB compressed and 32 MiB expanded, subject to measurement with a real generated catalogue. Keep current data on failure; update status explains the failure. No cache eviction solely because the user signs out or a periodic check fails.

## Core and app integration

Core needs typed sensor OID/type fields (currently untyped extension data), a catalogue reader/resolver and an installation store/updater behind interfaces. Expose resolution provenance and unresolved reasons without UI strings. The caller supplies storage, source settings, update permission and cancellation. Desktop and MCP must use the same catalogue version when bundled together; publish change notifications so each reader can reload atomically.

Desktop settings are installation-level and must be excluded from sign-out's profile deletion. Apply immediately on Apply / Apply & Save. The sensor view models show labels with the raw value available in details, retain raw values for graphs, and use only authoritative generic states for state colours. Turning the feature off restores current raw-value behaviour and clears in-memory resolved labels as well as files.

No changes are proposed here to SNMP polling, LibreNMS credentials, existing alert retrieval, app update scheduling or the 2.0.0 release pipeline.
