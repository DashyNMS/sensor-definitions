"""Compile automatically discovered PHP mappings with source-defined applicability."""
from pathlib import Path, PurePosixPath
import argparse
import json
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".deps"))

from php_analysis import Analyser, LimitExceeded, OidChoices, Template, Unknown, describe, source_structure


def safe_source(upstream, path):
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in path or ":" in path:
        raise ValueError("Unsafe source include path")
    resolved = (upstream / path).resolve()
    if not resolved.is_relative_to(upstream.resolve()):
        raise ValueError("Source include escapes the pinned checkout")
    return resolved


def routes(upstream, load_yaml, report=None):
    result = []
    report = [] if report is None else report
    router = upstream / "includes/discovery/sensors.inc.php"
    for file in sorted((upstream / "resources/definitions/os_detection").glob("*.yaml")):
        data = load_yaml(file.read_text(encoding="utf-8")) or {}
        os_name = data.get("os", file.stem)
        group_name = data.get("group") or ""
        context = {"os": os_name, "os_group": data.get("group")}
        if not isinstance(os_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", os_name):
            raise ValueError("Unsafe source OS identity")
        if not isinstance(group_name, str) or (group_name and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]*", group_name)):
            raise ValueError("Unsafe source OS group")
        def class_name(name):
            # LibreNMS\Util\StringHelpers::toClass; this naming rule is shared
            # by every OS and does not register any vendor/file individually.
            value = "".join(part.capitalize() for part in re.split(r"[-_ ]+", name.lower()))
            if len(value) > 1 and value[0].isdigit():
                value = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"][int(value[0])] + value[1].upper() + value[2:]
            return value
        modern = "LibreNMS/OS/" + class_name(os_name) + ".php"
        shared = "LibreNMS/OS/Shared/" + class_name(group_name) + ".php"
        selected = modern if (upstream / modern).is_file() else shared if (upstream / shared).is_file() else "LibreNMS/OS/Generic.php"
        if (upstream / selected).is_file():
            result.append({"path": selected, "context": context, "conditions": []})
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
            report.extend(analysis.problems)
            for include in analysis.includes:
                if safe_source(upstream, include["path"]).is_file():
                    result.append({"path": include["path"], "context": context, "conditions": include["conditions"]})
    expanded = []
    metadata = {}
    def follow(route, trail=()):
        path = route["path"]
        if path in trail:
            report.append({"path": path, "reason": "Cyclic source include"})
            return
        if len(trail) > 32 or len(expanded) >= 200000:
            raise LimitExceeded("Source include graph limit")
        if path not in metadata:
            source = safe_source(upstream, path).read_bytes()
            try:
                metadata[path] = (source, source_structure(source))
            except ValueError as error:
                report.append({"path": path, "reason": str(error)})
                return
        source, (parents, has_includes) = metadata[path]
        inherited_sources = []
        if path.startswith("LibreNMS/OS"):
            for parent in parents:
                if parent == "LibreNMS\\OS" or parent.startswith("LibreNMS\\OS\\"):
                    inherited = parent.replace("\\", "/") + ".php"
                    if safe_source(upstream, inherited).is_file():
                        inherited_sources.append(inherited)
                    else:
                        report.append({"path": path, "reason": "OS parent source is unavailable"})
                        return
                else:
                    report.append({"path": path, "reason": "OS parent lies outside the supported source namespace"})
                    return
        expanded.append(route)
        for inherited in inherited_sources:
            follow({"path": inherited, "context": route["context"], "conditions": route["conditions"]}, trail + (path,))
        if not has_includes:
            return
        analyser = Analyser(path, route["context"], routing=True)
        try:
            analyser.analyse(source)
            report.extend(analyser.problems)
            for included in analyser.includes:
                if safe_source(upstream, included["path"]).is_file():
                    follow({"path": included["path"], "context": route["context"],
                        "conditions": route["conditions"] + included["conditions"]}, trail + (path,))
        except (ValueError, TypeError, KeyError, IndexError) as error:
            report.append({"path": path, "reason": "Source routing analysis failed closed: " + str(error)})
    for route in result:
        follow(route)
    return expanded


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


def oid_options(value):
    if isinstance(value, OidChoices):
        return value.values
    if isinstance(value, Template):
        options = [[]]
        for part in value.parts:
            choices = part.values if isinstance(part, OidChoices) else [part]
            if len(options) * len(choices) > 64:
                raise LimitExceeded("Numeric OID alternative limit")
            options = [prefix + [choice] for prefix in options for choice in choices]
        return [Template(parts) for parts in options]
    return [value]


def oid_identity(value):
    if not isinstance(value, Template):
        return numeric_prefix(value), None
    prefix, suffix, dynamic = "", "", False
    for part in value.parts:
        if isinstance(part, Unknown):
            if suffix.strip("."):
                raise ValueError("Fixed OID component between dynamic spans")
            dynamic, suffix = True, ""
        elif isinstance(part, (str, int)):
            if dynamic:
                suffix += str(part)
            else:
                prefix += str(part)
        else:
            raise ValueError("Runtime or unsupported OID identity")
    if not dynamic:
        return numeric_prefix(prefix), None
    if not prefix.endswith("."):
        raise ValueError("Runtime or unsupported OID identity")
    if suffix.strip("."):
        if not suffix.startswith(".") or not re.fullmatch(r"\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))*", suffix) or len(suffix) > 1024:
            raise ValueError("Unsupported fixed OID suffix")
        return prefix.strip("."), suffix[1:]
    return prefix.strip("."), None


def compile_sources(upstream, report, definition, load_yaml):
    mappings, parameterised, analysed = [], [], set()
    for route in routes(upstream, load_yaml, report):
        path = route["path"]
        source = (upstream / path).read_bytes()
        analysed.add(path)
        if not re.search(rb"create_state_index\s*\(|SensorType::State|withStateTranslations", source):
            continue
        try:
            facts, problems = Analyser(path, route["context"]).analyse(source)
            report.extend(problems)
            for fact in facts:
                try:
                    for option in oid_options(fact["oid"]):
                        oid, suffix = oid_identity(option)
                        sensor_type = fact["sensorType"]
                        conditions = route["conditions"] + fact["conditions"]
                        if not isinstance(sensor_type, str) or conditions or suffix:
                            validated = definition(route["context"]["os"], "analysis-placeholder", oid, fact["states"], path, "analysis-placeholder")
                            parameterised.append({"path": path, "line": fact["line"], "context": route["context"], "conditions": conditions,
                                                  "sensorType": describe(sensor_type), "oidPrefix": oid, "states": validated["states"],
                                                  **({"oidSuffix": suffix} if suffix else {})})
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
