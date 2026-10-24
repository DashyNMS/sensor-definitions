# Official import coverage

Definitions in this pack come only from the pinned official LibreNMS repository. App users can select a separate compatible catalogue repository; that does not add custom/vendor inputs to this official build.

## Automatic extraction

The build inventories all OS discovery YAML and discovery/OS PHP inputs. It follows per-OS, group and RFC1628 routes, shared includes and declared OS class inheritance. Supported new files require no vendor registration or app change.

YAML preserves explicit `state_name` and otherwise uses the original `oid`, independently of the reading's `value`. Trailing index/noindex templates are handled structurally. Missing numeric OIDs use pinned SMI parsing of official MIB modules and imports, with ambiguity/cycle checks and provenance. No generated Python, PHP or downloaded instructions execute.

The PHP compiler handles literal/nested arrays, assignments and value-copy aliases, static destructuring/loops, match defaults and numeric OID alternatives, supported switch cases, state-index registration and modern Sensor/StateTranslation declarations. Runtime SNMP rows remain symbolic. Only source-derived row fields can widen a sensor-type selector; arbitrary unknown function results cannot become any-type rules. Uncertain coercions, unsupported control flow and runtime labels stay unresolved. Resource limits bound syntax, values, loops, branches, predicates and output.

## Matching and compatibility

Schema 1 contains exact OS/type/OID-prefix mappings. Schema 2 adds bounded type templates and source device conditions: exact strings, containment, presence, all/any and negation. Missing context remains unknown through negation. A fixed OID suffix after a variable index is preserved, including component boundaries and a non-empty index; it is never discarded into a broad prefix.

Numeric OID alternatives may expand only identities. They never combine alternative labels or severity tables. Source conflicts are omitted during generation; overlapping conflicting rules remain explicitly unresolved by the shared reader. Unknown numeric values never inherit a healthy state, and MIB labels alone never supply severity.

Both formats remain OS-sharded. Apps load only needed systems and retain bounded memory caches; MIBs and parser dependencies remain build inputs.

## Explicit boundaries and release gates

Some official PHP reads its translation labels or reference tables from live SNMP values, constructs identities through unsupported runtime transformations, or uses control-flow/aggregation patterns the bounded analyser cannot prove. A static pack cannot recover those remote values. Definitions absent from official LibreNMS are also outside this pack; neither device names nor nearby enum values are evidence for a label.

Every discovered source has a coverage status and reason. The reviewed baseline records current unsupported/partial source reasons rather than pretending all files are supported. New omissions, lost mappings or changed labels/severity stop normal builds. Diagnostic review builds cannot be published. Extend the reusable importer or review the specific exclusion before updating that baseline.

The normal supported path remains automatic: official LibreNMS release → pinned source → both catalogue formats → Windows/macOS/Linux validation → immutable matching-version release → atomic stable-feed promotion. A new unsupported construct stops that path for review instead of silently publishing incomplete or guessed mappings.

The initial contextual baseline also records conservative exclusions for nested loop control in Rittal and AirOS, runtime-derived APC and Commander Plus type identities, indirect Edgecos calls, and runtime context dependencies in Eurostor and Loop Telecom. These need further reusable analysis before their omitted mappings can be certified. Existing compatible catalogue fingerprints remain unchanged; recording an omission does not mark it as supported.
