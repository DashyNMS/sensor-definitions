# Sensor definitions design

The pack and shared Core reader implement the sharded protocol below. Desktop and MCP integration supplies installation settings and device context. Native packaging validation and future platform limitations are called out explicitly.

## Ownership and settings

The definitions repository owns data generation, provenance, validation and catalogue releases. Core owns matching, catalogue parsing, download validation, caching and change notifications. The app owns user controls and supplies an absolute installation data directory. No UI framework belongs in the catalogue repository or Core reader.

Desktop settings controls:

| Control | Behaviour |
| --- | --- |
| Use sensor definitions | Default off; enabling permits lookup and synchronisation |
| Source | Official DashyNMS repository or Custom repository |
| Custom repository | HTTPS repository URL; first adapter supports public GitHub repositories |
| Update definitions | Manual check, available while enabled |
| Status | Selected source, active version, last successful sync, storage path and any error |

Changing a repository does not itself download while the feature is off. The settings flow must explain that disabling removes the downloaded definitions. Existing Apply / Apply & Save behaviour should apply these choices consistently.

Store this preference outside the account profile and outside the removable definitions directory. Sign-out must not reset the preference, chosen repository or cache. The installation settings record contains `sensorDefinitions.enabled`, `sourceKind` and `customRepositoryUrl`; it contains no API tokens or account identifiers. Keep the custom repository choice when disabled so users can re-enable it without entering the URL again.

## Installation storage

The requirement is installation-local storage, not an account cache or the current working directory. Platform storage targets:

| Platform | Definitions directory |
| --- | --- |
| Windows per-user installer / extracted dev build | `<directory containing DashyNMS.exe>/sensor-definitions/` |
| macOS | `<directory containing DashyNMS.app>/DashyNMS.sensor-definitions/`, outside the signed app bundle |
| Linux AppImage | `<directory containing the AppImage>/DashyNMS.sensor-definitions/`, outside its mounted filesystem |

These paths need native validation before becoming the shipping contract. A Mac app bundle and an AppImage are not writable data folders. Their surrounding directories can also be protected. Do not request elevation or silently move the cache into a sign-out-cleared profile. If the installation directory is not writable, report that synchronisation is unavailable at that location and retain raw sensor readings. The supported remedy or explicit alternative installation-owned data path must be decided for protected installs before rollout.

An installation may retain several sources:

```text
<installation-data>/installation-settings.json
<definitions-root>/
  sources/<source-key>/index.json
  sources/<source-key>/checked.txt
  sources/<source-key>/objects/<compressed-shard-sha256>.gz
  sources/<source-key>/notices-<sha256>.txt
```

`source-key` is derived from the canonical repository/feed identity, never a user-controlled filesystem path. Keep definitions free of server names, device identifiers, readings, sign-in tokens and chat history. The desktop passes the resolved directory and enabled state to its bundled MCP process; MCP must not derive its own cache under the `mcp` executable directory. Use one installation updater and read-only consumers with a shared resolver.

Ordinary sign-out, account switching and app upgrades leave this data alone. Updaters and uninstall tooling need explicit preservation rules for the adjacent folder and installation settings. Under the requested deletion policy, uninstall must not independently purge definitions: the user disables the feature to remove them. Mobile cannot modify its installed application package; its later integration needs persistent app-owned storage excluded from sign-out cleanup.

## Disabling and deletion

Disabling takes effect immediately for resolution and synchronisation. Cancel in-flight work, invalidate its generation token and wait for the writer lock before removing the definitions root, including all source caches, staged downloads and catalogue backups. Do not delete unrelated installation files or the installation settings record.

A completed download must recheck enabled state, selected source and generation while holding the commit lock. It must never recreate the folder after disable. Re-enabling starts a fresh sync. Failed deletion leaves the feature off and exposes a pending-cleanup error; do not report that files were removed when they remain.

Use path containment checks against the resolved installation definitions root for every deletion. Symlinks/reparse points must not redirect cleanup outside that root. Replacing an active catalogue during an update is normal synchronisation; wholesale cache removal is tied to explicit disable, not expiry, sign-out or an independent uninstall cleanup.

## Custom repositories

Accept a compatible catalogue repository, not an arbitrary MIB repository or executable importer. Initial scope is public HTTPS GitHub repository URLs such as `https://github.com/example-org/sensor-definitions`. Normalise owner/repository identity and reject malformed URLs, embedded credentials, query strings and traversal. Other Git hosts can use a future feed adapter with the same data contract. Private repository authentication is outside the current adapter and must not reuse a LibreNMS API token.

Official and custom sources obey identical size, schema, provenance and integrity checks. A custom source is authoritative only when selected; do not silently merge it with official mappings. Switching source cancels obsolete updates and changes the generation token. Use a previously validated cache for the selected source, or raw readings while its first catalogue downloads. Keep other source caches until the feature is disabled. If the custom source fails, show the failure rather than quietly apply official definitions as if they came from the custom source.

Do not run code, PHP, shell scripts or MIB tooling downloaded from either source. Source import runs in the data repository's build process. Each catalogue release is independently versioned; end-user applications download the published data assets, not a Git checkout.

## Matching and interpretation

Version 1 matches state sensors using exact LibreNMS device `os`, exact sensor `sensor_type`, and a numeric OID prefix. All required selectors must be present and match. Normalise a leading dot on numeric OIDs; prefix comparison uses OID components, so `.1.2` cannot match `.1.20`. Match OS and sensor type as identifiers, not human-readable descriptions. Do not infer sensor identity from description text, IP addresses or vendor name alone.

Among candidates with the same exact identifiers, choose the longest matching OID prefix only if that leaves one definition. Equal-specificity conflicts are unresolved and fail catalogue validation when detectable. Never select whichever record happens to be first. Do not round a fractional reading to make it fit an enumeration. Integer values are encoded as canonical decimal strings in the catalogue to avoid JSON floating-point precision loss; Core only resolves values it can represent exactly from the API response.

Each resolved state has a label and an optional generic state: `ok`, `warning`, `critical` or `unknown`. `null` means no authoritative severity mapping is supplied, as can happen with a MIB-only enum. A label-only mapping must not turn an unknown state green or invent a threshold. These mappings describe sensor presentation; they do not create, recover or acknowledge LibreNMS alert records.

Schema 2 adds bounded sensor-type templates, a fixed OID suffix after a variable index, and source-derived device conditions for OS, hardware, version and sysObjectID. Predicates support equality, containment, presence and boolean groups. Missing metadata stays unknown, including through negation. The reader ranks matching OID prefix/suffix specificity and exact/template/any type selectors; equally ranked conflicting states remain ambiguous.

One verified match from the selected catalogue supplies the displayed label and authoritative generic state. Otherwise the raw reading remains visible with a structured unresolved reason. No server API enhancement or live discovery execution is required. Source revisions record provenance, not verified compatibility with every firmware version. Unsupported context expressions are reported and excluded.

## Import pipeline

Pin the official LibreNMS repository and exact commit. Extract YAML mappings and analyse PHP with a bounded Tree-sitter interpreter; never execute upstream PHP or unknown calls. Follow metadata, shared includes and declared OS inheritance without vendor registration. Resolve missing qualified numeric OIDs through pinned SMI syntax parsing and preserve provenance. Runtime translation labels, uncertain coercions and unsupported control flow remain explicit omissions. See [IMPORT-COVERAGE.md](IMPORT-COVERAGE.md) for supported constructs and boundaries.

Emit deterministic ordering, detect duplicate selectors/values, and validate each mapping against fixtures. Do not turn unsupported dynamic discovery logic into a guessed mapping. Produce a coverage report listing imported, unsupported and conflicting definitions. Reviewed corrections need their own provenance and regression fixture. No real customer network data goes into fixtures.

The draft example uses the documentation-only enterprise number 32473: [RFC 5612](https://www.rfc-editor.org/rfc/rfc5612). It must not appear in a production vendor catalogue.

## Versioning and update protocol

Separate `schemaVersion` from `catalogueVersion`. A schema-1 reader follows `feeds/v1/stable.json`. The contextual reader prefers `feeds/v2/stable.json`, falling back to v1 only when the v2 feed returns HTTP 404. Invalid feeds or other failures do not trigger a silent format downgrade. Use immutable tagged releases for catalogue assets; publish the channel pointer only after its referenced release is available and validated. A stable feed must not select a prerelease catalogue. The stable feed is the small OS index, not a monolithic catalogue. The catalogue version is in the index; OS data omits it so unchanged content can be reused across releases.

Abbreviated stable index:

```json
{
  "schemaVersion": 1,
  "catalogueVersion": "1.0.0",
  "notices": { "sha256": "<digest>", "downloadBytes": 35000 },
  "shards": [
    { "os": "ios", "sha256": "<compressed digest>", "downloadBytes": 1234, "expandedBytes": 12345, "definitions": 12 }
  ]
}
```

This abbreviated example uses placeholders; the index schema and generated manifests require full SHA-256 values. Readers construct shard and notice URLs from the selected repository and immutable version tag, so feeds cannot redirect downloads to arbitrary servers. The first implementation uses HTTPS and SHA-256, not signature verification. A checksum does not authenticate a compromised publisher; selecting a repository trusts that publisher. Signing/key rotation is a future extension and must not be claimed as implemented.

While enabled, update behaviour is one asynchronous check at startup if the last check was more than 24 hours ago, plus a manual update option. Repaint existing sensor values after an atomic catalogue swap; do not restart the app or discard selections. No update check should delay startup or require LibreNMS sign-in. Network failures keep the selected source's last validated catalogue. The offline-cache fix additionally reloads validated disk shards after a failed stale-feed refresh and backs off automatic retries for 15 minutes across the fleet; manual updates bypass that backoff.

Fetch only shards for requested device OS identifiers. Store compressed objects by hash within their source directory and validate each before atomic promotion of the index/loaded set. Limits are 1 MiB for the index/notices, 512 KiB compressed and 2 MiB expanded per OS shard. The lookup LRU holds at most 16 systems / 4 MiB of source JSON; parsed-object overhead and visible resolved rows are additional memory. Eviction from this memory cache never deletes disk data. A mixed fleet is processed one OS group at a time so even a network with more systems than the LRU limit resolves all its sensors. Keep current data on failure; update status explains the failure. No disk cache eviction solely because the user signs out or a periodic check fails.

## Core and app integration

Core provides typed sensor OID/type fields, a catalogue reader/resolver and an installation store/updater behind interfaces. Expose resolution provenance and unresolved reasons without UI strings. The caller supplies storage, source settings, update permission and cancellation. Desktop and MCP must use the same catalogue version when bundled together; publish change notifications so each reader can reload atomically.

Desktop settings are installation-level and must be excluded from sign-out's profile deletion. Apply immediately on Apply / Apply & Save. The sensor view models show labels with the raw value available in details, retain raw values for graphs, and use only authoritative generic states for state colours. Turning the feature off restores current raw-value behaviour and clears in-memory resolved labels as well as files.

No changes are proposed here to SNMP polling, LibreNMS credentials, existing alert retrieval, app update scheduling or the 2.0.0 release pipeline.
