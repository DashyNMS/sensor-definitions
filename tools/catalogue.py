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
    # Only a trailing index placeholder is understood. No expressions in OIDs.
    value = re.sub(r"\.?\{\{\s*\$index\s*\}\}$", "", value).strip(".")
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
        if not isinstance(label, str) or not label.strip() or "{{" in label or row["generic"] not in GENERIC:
            raise ValueError("Dynamic label or unknown generic state")
        result.append({"value": str(row["value"]), "label": label, "genericState": GENERIC[row["generic"]]})
    if len({row["value"] for row in result}) != len(result):
        raise ValueError("Duplicate state value")
    return sorted(result, key=lambda row: int(row["value"]))


def definition(os_name, sensor_type, oid, states, path, symbol):
    if not isinstance(sensor_type, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]+", sensor_type):
        raise ValueError("No explicit sensor type")
    match = {"os": os_name, "sensorClass": "state", "sensorType": sensor_type, "oidPrefix": oid_prefix(oid)}
    key = f"{os_name}/{sensor_type}/{match['oidPrefix']}"
    return {"id": key, "match": match, "states": state_rows(states),
            "sourceRefs": [{"sourceId": "librenms", "path": path, "symbol": symbol, "suppliesSeverity": True}]}


def import_yaml(upstream, report):
    result = []
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
                    # state_name, not a guessed MIB/value name, is sensor_type.
                    result.append(definition(file.stem, item.get("state_name"), item.get("num_oid"),
                                             item.get("states"), path, item.get("state_name", "")))
                except ValueError as error:
                    report.append({"path": path, "entry": index, "reason": str(error)})
        except (ValueError, yaml.YAMLError, AttributeError) as error:
            report.append({"path": path, "reason": f"Unsupported YAML: {error}"})
    return result


def php_literal_row(body):
    # Accept the entire row only when every field is a quoted string or integer.
    token = re.compile(r"\s*'(?P<key>[A-Za-z_]+)'\s*=>\s*(?:'(?P<string>(?:[^'\\]|\\.)*)'|(?P<int>-?[0-9]+))\s*,?\s*")
    result, pos = {}, 0
    while pos < len(body):
        item = token.match(body, pos)
        if item is None or item.end() == pos or item["key"] in result:
            raise ValueError("Non-literal PHP array")
        result[item["key"]] = int(item["int"]) if item["int"] is not None else item["string"].replace("\\'", "'").replace("\\\\", "\\")
        pos = item.end()
    return result


def import_cisco(upstream, report):
    path = "includes/discovery/sensors/state/cisco.inc.php"
    text = (upstream / path).read_text(encoding="utf-8")
    tables_match = re.search(r"\$tables\s*=\s*\[(.*?)\n\];", text, re.S)
    arms_match = re.search(r"\$states\s*=\s*match\s*\(\$state_name\)\s*\{(.*?)\n\s*\};", text, re.S)
    if not tables_match or not arms_match:
        raise ValueError("Pinned Cisco literal tables/match shape changed; review importer")
    tables = [php_literal_row(row) for row in re.findall(r"\[([^\[\]]+)\]", tables_match[1])]
    states = {}
    # Require commas between names; optional separators plus overlapping spaces
    # allow excessive backtracking when malformed input has no following arrow.
    arm = re.compile(r"('[^']+'(?:\s*,\s*'[^']+')*)\s*=>\s*\[(.*?)\n\s*\],", re.S)
    for match in arm.finditer(arms_match[1]):
        names = re.findall(r"'([^']+)'", match[1])
        bodies = re.findall(r"\[([^\[\]]+)\]", match[2])
        # Refuse expressions, function calls or conditionals between literal rows.
        residue = re.sub(r"\[[^\[\]]+\]", "", match[2]).replace(",", "").strip()
        if residue:
            report.append({"path": path, "symbol": names, "reason": "Dynamic PHP state arm"})
            continue
        try:
            rows = [php_literal_row(row) for row in bodies]
            state_rows(rows)
            for name in names:
                states[name] = rows
        except ValueError as error:
            report.append({"path": path, "symbol": names, "reason": str(error)})
    os_names = []
    for file in sorted((upstream / "resources/definitions/os_detection").glob("*.yaml")):
        # SafeLoader subclass; tests reject Python object tags and duplicate keys.
        doc = yaml.load(file.read_text(encoding="utf-8"), Loader=UniqueLoader) or {}  # nosec B506
        if doc.get("group") == "cisco":
            os_names.append(doc.get("os", file.stem))
    if not os_names:
        raise ValueError("No explicit Cisco OS group membership")
    result = []
    for table in tables:
        symbol = table.get("state_name")
        if symbol not in states:
            report.append({"path": path, "symbol": symbol, "reason": "No supported literal state arm"})
            continue
        for os_name in os_names:
            result.append(definition(os_name, symbol, table["num_oid"].rstrip("."), states[symbol], path, symbol))
    return result


def import_axis(upstream, report):
    path = "includes/discovery/sensors/state/axiscam.inc.php"
    text = (upstream / path).read_text(encoding="utf-8")
    assignments = list(re.finditer(r"\$cur_oid\s*=\s*([^;]+);", text))
    result = []
    for index, assignment in enumerate(assignments):
        block = text[assignment.end():assignments[index + 1].start() if index + 1 < len(assignments) else len(text)]
        try:
            oid = re.fullmatch(r"'([.0-9]+)'", assignment[1].strip())
            names = re.findall(r"\$state_name\s*=\s*([^;]+);", block)
            name = re.fullmatch(r"'([A-Za-z0-9_.:-]+)'", names[0].strip()) if len(names) == 1 else None
            states = re.search(r"\$states\s*=\s*\[(.*?)\n\s*\];", block, re.S)
            if not oid or not name or not states or len(re.findall(r"\$states\s*=", block)) != 1:
                raise ValueError("Dynamic or unsupported Axis identity/state table")
            residue = re.sub(r"\[[^\[\]]+\]", "", states[1]).replace(",", "").strip()
            if residue or not re.search(r"create_state_index\(\s*\$state_name\s*,\s*\$states\s*\)", block):
                raise ValueError("Non-literal or unregistered Axis state table")
            if not re.search(r"discover_sensor\(\s*null\s*,\s*SensorType::State\s*,\s*\$device\s*,\s*\$cur_oid\s*\.\s*\$index\s*,\s*\$index\s*,\s*\$state_name\s*,", block):
                raise ValueError("Unsupported Axis sensor identity")
            rows = [php_literal_row(body) for body in re.findall(r"\[([^\[\]]+)\]", states[1])]
            result.append(definition("axiscam", name[1], oid[1], rows, path, name[1]))
        except ValueError as error:
            report.append({"path": path, "entry": index, "reason": str(error)})
    if not assignments:
        report.append({"path": path, "reason": "No supported Axis OID assignments"})
    return result


def validate(catalogue, production=False):
    schema = json.loads((ROOT / "schemas/catalogue-v1.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(catalogue)
    source_ids = [source["id"] for source in catalogue["sources"]]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("Duplicate source ID")
    if production and any(source["kind"] == "synthetic" or source["licence"] == "NOASSERTION" for source in catalogue["sources"]):
        raise ValueError("Synthetic/unlicensed records cannot be published")
    ids, selectors = set(), set()
    for item in catalogue["definitions"]:
        selector = tuple(item["match"][key] for key in ("os", "sensorClass", "sensorType", "oidPrefix"))
        if item["id"] in ids or selector in selectors:
            raise ValueError("Duplicate or ambiguous definition")
        ids.add(item["id"])
        selectors.add(selector)
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


def build(upstream, version, output):
    lock = json.loads((ROOT / "sources/librenms.json").read_text())
    for required in lock["paths"]:
        if not (upstream / required).exists():
            raise ValueError("Pinned input checkout is incomplete: " + required)
    revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if revision != lock["revision"]:
        raise ValueError("Upstream checkout does not match sources/librenms.json")
    if subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
        raise ValueError("Upstream checkout has tracked modifications")
    report = []
    items = import_yaml(upstream, report) + import_cisco(upstream, report) + import_axis(upstream, report)
    # Identical duplicate imports combine their provenance; conflicting ones are omitted.
    grouped = collections.defaultdict(list)
    for item in items:
        grouped[tuple(item["match"].values())].append(item)
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
    catalogue = {"schemaVersion": 1,
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
    manifest = {"schemaVersion": 1, "catalogueVersion": version, "shards": shards,
                "notices": {"sha256": hashlib.sha256(notices).hexdigest(), "downloadBytes": len(notices)}}
    jsonschema.Draft202012Validator(json.loads((ROOT / "schemas/index-v1.schema.json").read_text())).validate(manifest)
    (output / "manifest.json").write_bytes(encode(manifest))
    coverage = {"definitions": len(definitions), "systems": len({item["match"]["os"] for item in definitions}),
                "upstreamRevision": revision, "unsupported": report}
    def load_inventory_yaml(text):
        try:
            return yaml.load(text, Loader=UniqueLoader)  # nosec B506
        except yaml.YAMLError as error:
            raise ValueError(str(error)) from error
    coverage["inventory"] = source_inventory.collect(upstream, definitions, report, load_inventory_yaml)
    (output / "coverage.json").write_bytes(encode(coverage))
    print(json.dumps({key: value for key, value in coverage.items() if key not in ("unsupported", "inventory")} | {"unsupported": len(report), "sourceStatus": coverage["inventory"]["totals"], "phpSources": coverage["inventory"]["phpSources"], "shardBytes": sum(item["downloadBytes"] for item in shards)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("build")
    command.add_argument("--upstream", type=Path, required=True)
    command.add_argument("--version", required=True)
    command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.upstream.resolve(), args.version, args.output.resolve())


if __name__ == "__main__":
    main()
