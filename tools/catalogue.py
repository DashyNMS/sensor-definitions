"""Build data from pinned static discovery literals; never execute upstream code."""
from __future__ import annotations
import argparse
import collections
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / ".deps"))
import yaml
import jsonschema
import source_inventory

GENERIC = {0: "ok", 1: "warning", 2: "critical", 3: "unknown"}
OID = re.compile(r"[0-2](?:\.(?:0|[1-9][0-9]*))+")


class UniqueLoader(yaml.SafeLoader):
    pass


# Discovery labels such as off/on are strings in YAML 1.2. PyYAML's default
# YAML 1.1 resolver otherwise turns them into booleans and drops valid mappings.
UniqueLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in resolvers if tag != "tag:yaml.org,2002:bool"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
UniqueLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
UniqueLoader.add_constructor("tag:yaml.org,2002:value", lambda loader, node: loader.construct_scalar(node))


def oid_prefix(value):
    if not isinstance(value, str):
        raise ValueError("No explicit numeric OID")
    # LibreNMS uses noindex to suppress a dynamic suffix on a fixed OID.
    # Only these trailing placeholders are supported; no arbitrary expressions.
    value = re.sub(r"\.?\{\{\s*\$(?:index|noindex)\s*\}\}$", "", value).strip(".")
    if len(value) > 1024:
        raise ValueError("OID size limit")
    if not OID.fullmatch(value):
        raise ValueError("Dynamic or malformed numeric OID")
    return value


def state_rows(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("No literal state list")
    result = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get("value")) is not int or type(row.get("generic")) is not int:
            raise ValueError("Non-integer state or severity")
        label = row.get("descr")
        if isinstance(label, str) and len(label) > 1024:
            raise ValueError("State label size limit")
        if not isinstance(label, str) or not label.strip() or "{{" in label or row["generic"] not in GENERIC:
            raise ValueError("Dynamic label or unknown generic state")
        result.append({"value": str(row["value"]), "label": label, "genericState": GENERIC[row["generic"]]})
    if len({row["value"] for row in result}) != len(result):
        raise ValueError("Duplicate state value")
    return sorted(result, key=lambda row: int(row["value"]))


def definition(os_name, sensor_type, oid, states, path, symbol):
    if not isinstance(sensor_type, str) or len(sensor_type) > 256 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", sensor_type):
        raise ValueError("No explicit sensor type")
    match = {"os": os_name, "sensorClass": "state", "sensorType": sensor_type, "oidPrefix": oid_prefix(oid)}
    key = f"{os_name}/{sensor_type}/{match['oidPrefix']}"
    return {"id": key, "match": match, "states": state_rows(states),
            "sourceRefs": [{"sourceId": "librenms", "path": path, "symbol": symbol, "suppliesSeverity": True}]}


def import_yaml(upstream, report):
    result = []
    resolver = None
    for file in sorted((upstream / "resources/definitions/os_discovery").glob("*.yaml")):
        path = file.relative_to(upstream).as_posix()
        try:
            # SafeLoader subclass; tests reject Python object tags and duplicate keys.
            doc = yaml.load(file.read_text(encoding="utf-8"), Loader=UniqueLoader) or {}  # nosec B506
            state = (doc.get("modules", {}).get("sensors", {}) or {}).get("state", {}) or {}
            rows = state.get("data", [])
            defaults = {k: v for k, v in state.items() if k != "data"}
            for index, item in enumerate(rows):
                try:
                    if not isinstance(item, dict):
                        raise ValueError("Non-mapping state entry")
                    item = defaults | item
                    # LibreNMS uses state_name ?? oid, independently of value.
                    sensor_type = item.get("state_name") if item.get("state_name") is not None else item.get("oid")
                    numeric = item.get("num_oid")
                    if isinstance(numeric, str) and "$noindex" in numeric and "noindex" in item:
                        raise ValueError("Explicit noindex context requires runtime resolution")
                    textual = item.get("value") if item.get("value") is not None else item.get("oid")
                    mib_paths = set()
                    if not numeric:
                        from mib_resolution import MibResolver
                        resolver = resolver or MibResolver(upstream)
                        if not isinstance(textual, str):
                            raise ValueError("No textual OID for numeric resolution")
                        if "::" not in textual:
                            raise ValueError("Unqualified textual OID requires explicit MIB selection")
                        resolver.used.clear()
                        numeric = resolver.oid(textual)
                        mib_paths = set(resolver.used)
                    mapped = definition(file.stem, sensor_type, numeric, item.get("states"), path, sensor_type)
                    mapped["sourceRefs"].extend({"sourceId": "librenms", "path": source_path,
                        "symbol": textual, "suppliesSeverity": False} for source_path in sorted(mib_paths))
                    result.append(mapped)
                except ValueError as error:
                    report.append({"path": path, "entry": index, "reason": str(error)})
        except (ValueError, yaml.YAMLError, AttributeError) as error:
            report.append({"path": path, "reason": f"Unsupported YAML: {error}"})
    return result


def selector(match):
    normalised = dict(match)
    normalised.setdefault("typeMatch", "exact")
    if not normalised.get("conditions"):
        normalised.pop("conditions", None)
    return json.dumps(normalised, sort_keys=True)


def validate(catalogue, production=False):
    version = catalogue.get("schemaVersion")
    if version not in (1, 2):
        raise ValueError("Unsupported catalogue schema")
    schema = json.loads((ROOT / f"schemas/catalogue-v{version}.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(catalogue)
    source_ids = [source["id"] for source in catalogue["sources"]]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("Duplicate source ID")
    if production and any(source["kind"] == "synthetic" or source["licence"] == "NOASSERTION" for source in catalogue["sources"]):
        raise ValueError("Synthetic/unlicensed records cannot be published")
    ids, selectors = set(), set()
    for item in catalogue["definitions"]:
        selected = selector(item["match"])
        if item["id"] in ids or selected in selectors:
            raise ValueError("Duplicate or ambiguous definition")
        ids.add(item["id"])
        selectors.add(selected)
        if len(item["id"]) > 512:
            raise ValueError("Sensor definition ID size limit")
        if version == 2:
            from context_rules import condition
            match = item["match"]
            kind = match.get("typeMatch", "exact")
            if kind == "any" and match["sensorType"] != "*":
                raise ValueError("Invalid any-type selector")
            if kind == "template" and (not 0 < match["sensorType"].count("*") <= 8):
                raise ValueError("Invalid sensor type template")
            for predicate in match.get("conditions") or []:
                condition(predicate)
        if len({state["value"] for state in item["states"]}) != len(item["states"]):
            raise ValueError("Duplicate state value")
        if any(ref["sourceId"] not in source_ids for ref in item["sourceRefs"]):
            raise ValueError("Missing provenance")
        if any(state["genericState"] is not None for state in item["states"]) and not any(ref["suppliesSeverity"] for ref in item["sourceRefs"]):
            raise ValueError("Severity has no authoritative source")


def encode(catalogue):
    return json.dumps(catalogue, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def compress(raw):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as stream:
        stream.write(raw)
    return buffer.getvalue()


def build(upstream, version, output, review_coverage=False):
    lock = json.loads((ROOT / "sources/librenms.json").read_text())
    if lock["repository"] != "https://github.com/librenms/librenms":
        raise ValueError("Official catalogue inputs must come from LibreNMS")
    for required in lock["paths"]:
        if not (upstream / required).exists():
            raise ValueError("Pinned input checkout is incomplete: " + required)
    revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if revision != lock["revision"]:
        raise ValueError("Upstream checkout does not match sources/librenms.json")
    if subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
        raise ValueError("Upstream checkout has tracked modifications")
    report = []
    from php_compiler import compile_sources
    from context_rules import definition as rule_definition
    yaml_items = import_yaml(upstream, report)
    exact, rules = compile_sources(upstream, report, definition,
        lambda text: yaml.load(text, Loader=UniqueLoader))  # nosec B506
    contextual = []
    for rule in rules:
        try:
            item = rule_definition(rule)
            if item is not None:
                contextual.append(item)
        except ValueError as error:
            report.append({"path": rule["path"], "line": rule["line"], "reason": str(error)})
    # Older clients keep receiving exact, unconditional mappings. Context must
    # never be discarded to make a new rule fit a schema-1 reader.
    compatible_report = report + [{"path": item["sourceRefs"][0]["path"], "symbol": item["sourceRefs"][0]["symbol"],
        "reason": "Source context requires a schema-2 reader"} for item in contextual]
    write_release(upstream, lock, version, output, yaml_items + exact, compatible_report, 1, review_coverage)
    write_release(upstream, lock, version, output / "v2", yaml_items + exact + contextual, report, 2, review_coverage)


def write_release(upstream, lock, version, output, items, report, schema_version, review_coverage=False):
    report = [json.loads(item) for item in sorted({json.dumps(item, sort_keys=True) for item in report})]
    revision = lock["revision"]
    # Identical duplicate imports combine their provenance; conflicting ones are omitted.
    grouped = collections.defaultdict(list)
    for item in items:
        grouped[selector(item["match"])].append(item)
    definitions = []
    for group in grouped.values():
        first = group[0]
        if any(item["states"] != first["states"] for item in group[1:]):
            report.append({"id": first["id"], "reason": "Conflicting mappings omitted"})
            continue
        first["sourceRefs"] = sorted({json.dumps(ref, sort_keys=True) for item in group for ref in item["sourceRefs"]})
        first["sourceRefs"] = [json.loads(ref) for ref in first["sourceRefs"]]
        definitions.append(first)
    licence = (upstream / "LICENSE.txt").read_text(encoding="utf-8")
    catalogue = {"schemaVersion": schema_version,
                 "sources": [{"id": "librenms", "kind": "librenms-discovery", "location": lock["repository"],
                              "revision": revision, "licence": lock["licence"], "notice": licence}],
                 "definitions": sorted(definitions, key=lambda item: item["id"])}
    validate(catalogue, production=True)
    output.mkdir(parents=True, exist_ok=True)
    shards = []
    shard_sources = [dict(source, notice="See notices.txt in this catalogue release.") for source in catalogue["sources"]]
    for os_name in sorted({item["match"]["os"] for item in definitions}):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", os_name):
            raise ValueError("Unsafe OS file identifier")
        shard = dict(catalogue, sources=shard_sources, definitions=[item for item in definitions if item["match"]["os"] == os_name])
        raw = encode(shard)
        compressed = compress(raw)
        if len(raw) > 2 * 1024 * 1024 or len(compressed) > 512 * 1024:
            raise ValueError("OS shard exceeds reader size limits")
        (output / "os").mkdir(exist_ok=True)
        (output / "os" / f"{os_name}.json.gz").write_bytes(compressed)
        shards.append({"os": os_name, "sha256": hashlib.sha256(compressed).hexdigest(),
                       "downloadBytes": len(compressed), "expandedBytes": len(raw), "definitions": len(shard["definitions"])})
    notices = ("LibreNMS-derived sensor mappings\nSource: " + lock["repository"] + "\nRevision: " + revision + "\n\n" + licence).encode("utf-8")
    (output / "notices.txt").write_bytes(notices)
    manifest = {"schemaVersion": schema_version, "catalogueVersion": version, "shards": shards,
                "notices": {"sha256": hashlib.sha256(notices).hexdigest(), "downloadBytes": len(notices)}}
    jsonschema.Draft202012Validator(json.loads((ROOT / f"schemas/index-v{schema_version}.schema.json").read_text())).validate(manifest)
    (output / "manifest.json").write_bytes(encode(manifest))
    coverage = {"definitions": len(definitions), "systems": len({item["match"]["os"] for item in definitions}),
                "upstreamRevision": revision, "unsupported": report}
    def load_inventory_yaml(text):
        try:
            return yaml.load(text, Loader=UniqueLoader)  # nosec B506
        except yaml.YAMLError as error:
            raise ValueError(str(error)) from error
    coverage["inventory"] = source_inventory.collect(upstream, definitions, report, load_inventory_yaml)
    from coverage_gate import check
    baseline = json.loads((ROOT / "sources/coverage-baseline.json").read_text())
    try:
        coverage["gate"] = {"status": "passed", **check(definitions, coverage["inventory"], baseline)}
    except ValueError as error:
        if not review_coverage:
            raise
        coverage["gate"] = {"status": "review-required", "reason": str(error)}
    (output / "coverage.json").write_bytes(encode(coverage))
    print(json.dumps({key: value for key, value in coverage.items() if key not in ("unsupported", "inventory")} | {"unsupported": len(report), "sourceStatus": coverage["inventory"]["totals"], "phpSources": coverage["inventory"]["phpSources"], "shardBytes": sum(item["downloadBytes"] for item in shards)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("build")
    command.add_argument("--upstream", type=Path, required=True)
    command.add_argument("--version", required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--review-coverage", action="store_true", help="Write non-publishable diagnostics for a reviewed baseline update")
    args = parser.parse_args()
    build(args.upstream.resolve(), args.version, args.output.resolve(), args.review_coverage)


if __name__ == "__main__":
    main()
