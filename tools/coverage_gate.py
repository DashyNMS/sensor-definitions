"""Reject unreviewed source omissions and regressions against the active catalogue."""
import hashlib
import json


def semantic_hash(item):
    match = dict(item["match"])
    match.setdefault("typeMatch", "exact")
    if not match.get("conditions"):
        match.pop("conditions", None)
    data = {"match": match, "states": sorted(item["states"], key=lambda state: int(state["value"]))}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def check(definitions, inventory, baseline):
    actual = {item["id"]: semantic_hash(item) for item in definitions}
    lost = sorted(set(baseline["definitions"]) - set(actual))
    changed = sorted(key for key, value in baseline["definitions"].items() if key in actual and actual[key] != value)
    if lost or changed:
        raise ValueError(f"Catalogue regression needs review: {len(lost)} missing definitions, {len(changed)} changed mappings")
    allowed = baseline["sourceOmissions"]
    unexpected = []
    for source in inventory["sources"]:
        if source["status"] not in ("unsupported", "partial"):
            continue
        for reason in source["reasons"]:
            if reason == "Source context requires a schema-2 reader":
                continue
            if reason not in allowed.get(source["path"], []):
                unexpected.append({"path": source["path"], "reason": reason})
    if unexpected:
        raise ValueError(f"Unreviewed source omissions: {len(unexpected)}; update the reusable importer or review the coverage baseline")
    return {"preservedDefinitions": len(baseline["definitions"]), "newDefinitions": len(actual) - len(baseline["definitions"]),
            "unreviewedOmissions": 0}
