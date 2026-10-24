"""Account for every pinned discovery input, including unsupported sources."""
from collections import Counter, defaultdict
import hashlib
import re


def collect(upstream, definitions, unsupported, load_yaml):
    mappings = Counter(ref["path"] for item in definitions for ref in item["sourceRefs"])
    problems = defaultdict(list)
    for item in unsupported:
        if "path" in item:
            problems[item["path"]].append(item["reason"])
    sources = []
    for file in sorted((upstream / "resources/definitions/os_discovery").glob("*.yaml")):
        path = file.relative_to(upstream).as_posix()
        try:
            doc = load_yaml(file.read_text(encoding="utf-8")) or {}
            state = (doc.get("modules", {}).get("sensors", {}) or {}).get("state", {}) or {}
            count = len(state.get("data", []))
            relevant = bool(state)
            error = None
        except (ValueError, AttributeError, TypeError) as ex:
            relevant, count, error = True, 0, str(ex)
        status = "partial" if mappings[path] and problems[path] else "imported" if mappings[path] else "unsupported" if relevant else "no-state-definitions"
        sources.append({"path": path, "kind": "yaml", "status": status, "entries": count,
                        "mappings": mappings[path], "reasons": sorted(set(problems[path] or ([error] if error else ["No supported state mapping"] if relevant and not mappings[path] else [])))})
    state_files = set((upstream / "includes/discovery/sensors/state").glob("*.php"))
    candidates = set(state_files)
    marker = re.compile(r"create_state_index\s*\(|discover_state\s*\(|SensorType::State|SensorState::|StateTranslation::")
    for directory in (upstream / "includes/discovery", upstream / "LibreNMS/OS"):
        for file in directory.rglob("*.php"):
            candidates.add(file)
    if (upstream / "LibreNMS/OS.php").is_file():
        candidates.add(upstream / "LibreNMS/OS.php")
    for file in sorted(candidates):
        path = file.relative_to(upstream).as_posix()
        reasons = sorted(set(problems[path]))
        status = "partial" if mappings[path] and reasons else "imported" if mappings[path] else "unsupported"
        relevant = file in state_files or bool(reasons) or bool(marker.search(file.read_text(encoding="utf-8")))
        if not relevant and not mappings[path]:
            status = "no-static-state-marker"
        if not mappings[path] and not reasons:
            reasons = ["PHP discovery source has no extracted state mappings"] if relevant else []
        sources.append({"path": path, "kind": "php", "status": status, "mappings": mappings[path], "reasons": reasons})
    paths = {item["path"] for item in sources}
    for path in sorted(set(mappings) - paths):
        file = upstream / path
        if path.startswith("mibs/") and ".." not in file.parts and file.is_file():
            sources.append({"path": path, "kind": "mib", "status": "imported", "mappings": mappings[path], "reasons": []})
            paths.add(path)
    missing = sorted(set(mappings) - paths)
    if missing:
        raise ValueError("Extracted provenance is absent from the input inventory: " + ", ".join(missing))
    for item in sources:
        item["sha256"] = hashlib.sha256((upstream / item["path"]).read_bytes()).hexdigest()
    return {"sources": sources, "totals": dict(sorted(Counter(item["status"] for item in sources).items())),
            "phpSources": len(candidates), "legacyStatePhpSources": len(state_files), "unaccounted": len(missing)}
