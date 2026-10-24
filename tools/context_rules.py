"""Compile symbolic discoveries to bounded, non-executable catalogue selectors."""
import hashlib
import json


def condition(node, depth=0, budget=None):
    budget = [0] if budget is None else budget
    budget[0] += 1
    if depth > 8 or budget[0] > 128:
        raise ValueError("Source condition nesting limit")
    if type(node) is bool:
        return node
    if not isinstance(node, dict):
        raise ValueError("Unsupported source condition")
    if set(node) in ({"all"}, {"any"}):
        operator = next(iter(node))
        children = [condition(child, depth + 1, budget) for child in node[operator]]
        if len(children) > 16:
            raise ValueError("Source condition group size limit")
        if operator == "all" and False in children:
            return False
        if operator == "any" and True in children:
            return True
        children = [child for child in children if type(child) is not bool]
        if not children:
            return operator == "all"
        return {operator: children}
    if set(node) == {"not"}:
        child = condition(node["not"], depth + 1, budget)
        return not child if type(child) is bool else {"not": child}
    if node.get("field") not in ("os", "hardware", "version", "sysObjectID"):
        raise ValueError("Unsupported source context dependency")
    if node.get("op") == "present" and set(node) == {"field", "op"}:
        return node
    if (node.get("op") in ("equals", "notEquals", "contains") and set(node) == {"field", "op", "value"}
            and isinstance(node["value"], str) and 0 < len(node["value"]) <= 1024):
        return node
    raise ValueError("Unsupported source context operation")


def type_selector(value):
    if isinstance(value, str):
        return value, "exact"
    if isinstance(value, dict) and set(value) == {"runtime", "origin"} and value["origin"] == "snmp-field":
        return "*", "any"
    if isinstance(value, dict) and set(value) == {"parts"}:
        parts = []
        for part in value["parts"]:
            if isinstance(part, (str, int)) and "*" not in str(part):
                parts.append(str(part))
            elif isinstance(part, dict) and set(part) == {"runtime", "origin"} and part["origin"] in ("snmp-field", "snmp-index"):
                if not parts or parts[-1] != "*":
                    parts.append("*")
            else:
                raise ValueError("Unsupported sensor type template")
        pattern = "".join(parts)
        if pattern == "*":
            return pattern, "any"
        if 0 < len(pattern) <= 256 and 0 < pattern.count("*") <= 8:
            return pattern, "template"
    raise ValueError("Unsupported sensor type identity")


def definition(rule):
    sensor_type, kind = type_selector(rule["sensorType"])
    if not isinstance(sensor_type, str) or not 0 < len(sensor_type) <= 256:
        raise ValueError("Sensor type size limit")
    conditions = [condition(node) for node in rule["conditions"]]
    if False in conditions:
        return None
    conditions = [node for node in conditions if type(node) is not bool]
    if len(conditions) > 16:
        raise ValueError("Source condition count limit")
    match = {"os": rule["context"]["os"], "sensorClass": "state", "sensorType": sensor_type,
             "typeMatch": kind, "oidPrefix": rule["oidPrefix"]}
    if conditions:
        match["conditions"] = conditions
    if rule.get("oidSuffix"):
        match["oidSuffix"] = rule["oidSuffix"]
    digest = hashlib.sha256(json.dumps(match, sort_keys=True).encode()).hexdigest()
    return {"id": match["os"] + "/rule/" + digest, "match": match, "states": rule["states"],
            "sourceRefs": [{"sourceId": "librenms", "path": rule["path"], "symbol": sensor_type, "suppliesSeverity": True}]}
