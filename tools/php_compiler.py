"""Compile automatically discovered PHP mappings with source-defined applicability."""
from pathlib import Path, PurePosixPath
import argparse
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".deps"))

from php_analysis import Analyser, LimitExceeded, Template, Unknown, describe


def routes(upstream, load_yaml):
    result = []
    router = upstream / "includes/discovery/sensors.inc.php"
    for file in sorted((upstream / "resources/definitions/os_detection").glob("*.yaml")):
        data = load_yaml(file.read_text(encoding="utf-8")) or {}
        os_name = data.get("os", file.stem)
        context = {"os": os_name, "os_group": data.get("group", "")}
        names = [os_name, *([data["group"]] if isinstance(data.get("group"), str) else [])]
        if data.get("rfc1628_compat") is True:
            names.append("rfc1628")
        for name in names:
            path = "includes/discovery/sensors/state/" + name + ".inc.php"
            if (upstream / path).is_file():
                result.append({"path": path, "context": context, "conditions": []})
        if router.is_file():
            analysis = Analyser(router.relative_to(upstream).as_posix(), context, routing=True)
            analysis.analyse(router.read_bytes())
            for include in analysis.includes:
                path = PurePosixPath(include["path"])
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("Unsafe source include path")
                if (upstream / include["path"]).is_file():
                    result.append({"path": include["path"], "context": context, "conditions": include["conditions"]})
    return result


def numeric_prefix(value):
    if isinstance(value, str):
        return value.strip(".")
    if isinstance(value, Template):
        prefix = ""
        dynamic = False
        for part in value.parts:
            if isinstance(part, (str, int)) and not dynamic:
                prefix += str(part)
            elif isinstance(part, (Unknown, Template)):
                dynamic = True
            elif isinstance(part, (str, int)) and str(part).strip("."):
                raise ValueError("Dynamic OID component before a fixed suffix")
        if dynamic and prefix.endswith("."):
            return prefix.strip(".")
    raise ValueError("Runtime or unsupported OID identity")


def compile_sources(upstream, report, definition, load_yaml):
    mappings, parameterised, analysed = [], [], set()
    for route in routes(upstream, load_yaml):
        path = route["path"]
        source = (upstream / path).read_bytes()
        if not re.search(rb"create_state_index\s*\(|SensorType::State|withStateTranslations", source):
            continue
        analysed.add(path)
        try:
            facts, problems = Analyser(path, route["context"]).analyse(source)
            report.extend(problems)
            for fact in facts:
                try:
                    oid = numeric_prefix(fact["oid"])
                    sensor_type = fact["sensorType"]
                    conditions = route["conditions"] + fact["conditions"]
                    if not isinstance(sensor_type, str) or conditions:
                        validated = definition(route["context"]["os"], "analysis-placeholder", oid, fact["states"], path, "analysis-placeholder")
                        parameterised.append({"path": path, "line": fact["line"], "context": route["context"], "conditions": conditions,
                                              "sensorType": describe(sensor_type), "oidPrefix": oid, "states": validated["states"]})
                        continue
                    mappings.append(definition(route["context"]["os"], sensor_type, oid, fact["states"], path, sensor_type))
                except ValueError as error:
                    report.append({"path": path, "line": fact["line"], "reason": str(error)})
        except (ValueError, LimitExceeded, TypeError, KeyError, IndexError) as error:
            report.append({"path": path, "reason": "PHP analysis failed closed: " + str(error)})
    # Every state module is parsed even if no current OS routes to it. New files
    # therefore need no registration and unsupported syntax cannot disappear.
    for file in sorted((upstream / "includes/discovery/sensors/state").glob("*.php")):
        path = file.relative_to(upstream).as_posix()
        if path not in analysed:
            try:
                Analyser(path).analyse(file.read_bytes())
                report.append({"path": path, "reason": "No source-defined OS route"})
            except (ValueError, LimitExceeded) as error:
                report.append({"path": path, "reason": "PHP analysis failed closed: " + str(error)})
    return mappings, parameterised


def analyse(upstream):
    # This intermediate report is deliberately separate from the published v1
    # catalogue. Rules must never lose applicability just to fit an old reader.
    import catalogue
    report = []
    mappings, rules = compile_sources(upstream, report, catalogue.definition,
        lambda text: catalogue.yaml.load(text, Loader=catalogue.UniqueLoader))  # nosec B506
    def canonical(items):
        return [json.loads(item) for item in sorted({json.dumps(item, sort_keys=True) for item in items})]
    return {"analysisOnly": True, "candidateDefinitions": canonical(mappings),
            "unresolvedRules": canonical(rules), "problems": canonical(report)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analyse(args.upstream), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
