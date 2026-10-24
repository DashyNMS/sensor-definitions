"""Bounded static PHP analysis. Unknown calls are data, never executed."""
from copy import deepcopy
import re

from tree_sitter import Language, Parser
import tree_sitter_php


class Unknown:
    def __init__(self, expression):
        self.expression = expression

    def __repr__(self):
        return "Unknown(" + repr(self.expression) + ")"


class Template:
    def __init__(self, parts):
        self.parts = []
        for part in parts:
            self.parts.extend(part.parts if isinstance(part, Template) else [part])

    def __repr__(self):
        return "Template(" + repr(self.parts) + ")"


class LimitExceeded(ValueError):
    pass


def known(value):
    if isinstance(value, (Unknown, Template)):
        return False
    if isinstance(value, dict):
        return all(known(item) for item in value.values())
    return True


def identity(value):
    if isinstance(value, Unknown):
        return ("runtime", value.expression)
    if isinstance(value, Template):
        return tuple(identity(part) for part in value.parts)
    if isinstance(value, dict):
        return ("unsupported", repr(value))
    return value


def describe(value):
    if isinstance(value, Unknown):
        return {"runtime": value.expression}
    if isinstance(value, Template):
        return {"parts": [describe(part) for part in value.parts]}
    return value


def bounded(value, depth=0):
    if depth > 64:
        raise LimitExceeded("PHP value nesting limit")
    if isinstance(value, str) and len(value) > 65536:
        raise LimitExceeded("PHP string size limit")
    if type(value) is int and value.bit_length() > 128:
        raise LimitExceeded("PHP integer size limit")
    if isinstance(value, Template):
        if len(value.parts) > 256:
            raise LimitExceeded("PHP template size limit")
        for part in value.parts:
            bounded(part, depth + 1)
    if isinstance(value, dict):
        if len(value) > 4096:
            raise LimitExceeded("PHP array size limit")
        for key, item in value.items():
            bounded(key, depth + 1)
            bounded(item, depth + 1)
    return value


class Analyser:
    def __init__(self, path="fixture.php", context=None, routing=False):
        self.path = path
        self.context = context or {}
        self.facts = []
        self.problems = []
        self.steps = 0
        self.routing = routing
        self.includes = []

    def condition(self, node, env):
        if node.type == "parenthesized_expression":
            return self.condition(node.named_children[0], env)
        if node.type == "binary_expression":
            left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
            operator = node.text[left.end_byte - node.start_byte:right.start_byte - node.start_byte].decode().strip()
            if operator in ("&&", "||"):
                return {"all" if operator == "&&" else "any": [self.condition(left, env), self.condition(right, env)]}
            if operator in ("==", "===", "!=", "!==") and left.type == "subscript_expression":
                children = left.named_children
                if self.text(children[0]) == "$device" and len(children) == 2:
                    field, expected = self.expr(children[1], env), self.expr(right, env)
                    if field in ("os", "os_group", "hardware", "version", "sysObjectID") and isinstance(expected, str):
                        return {"field": field, "op": "equals" if operator in ("==", "===") else "notEquals", "value": expected}
        if node.type == "function_call_expression":
            name = self.text(node.child_by_field_name("function"))
            arguments = node.child_by_field_name("arguments").named_children
            if arguments:
                value_node = arguments[0].named_children[0]
                if value_node.type == "subscript_expression" and self.text(value_node.named_children[0]) == "$device":
                    field = self.expr(value_node.named_children[1], env)
                    if name == "isset" and field in ("os", "hardware", "version", "sysObjectID", "os_group"):
                        return {"field": field, "op": "present"}
                    if name in ("strstr", "str_contains") and len(arguments) == 2:
                        expected = self.expr(arguments[1].named_children[0], env)
                        if isinstance(expected, str) and field in ("hardware", "version", "sysObjectID"):
                            return {"field": field, "op": "contains", "value": expected}
        value = self.expr(node, env)
        return bool(value) if known(value) else {"unsupported": self.text(node)}

    def step(self):
        self.steps += 1
        if self.steps > 200000 or len(self.facts) > 4096:
            raise LimitExceeded("PHP analysis resource limit")

    @staticmethod
    def text(node):
        return node.text.decode("utf-8") if node else ""

    def args(self, node, env):
        arguments = node.child_by_field_name("arguments") or next((child for child in node.named_children if child.type == "arguments"), None)
        return [self.expr(item.named_children[-1], env) for item in arguments.named_children if item.type == "argument"] if arguments else []

    def expr(self, node, env):
        self.step()
        if node is None:
            return None
        kind, text = node.type, self.text(node)
        children = node.named_children
        if kind in ("parenthesized_expression", "argument"):
            return self.expr(children[0], env)
        if kind == "integer":
            literal = text.replace("_", "")
            if literal.startswith(("0x", "0X", "0b", "0B", "0o", "0O")):
                return int(literal, 0)
            return int(literal, 8 if len(literal) > 1 and literal.startswith("0") else 10)
        if kind == "boolean":
            return text.lower() == "true"
        if kind == "null":
            return None
        if kind == "string":
            return text[1:-1].replace("\\'", "'").replace("\\\\", "\\")
        if kind == "encapsed_string":
            parts = [self.text(item) if item.type == "string_content" else self.expr(item, env) for item in children]
            return "".join(str(part) for part in parts) if all(known(part) for part in parts) else Template(parts)
        if kind == "variable_name":
            return env.get(text, Unknown(text))
        if kind == "array_creation_expression":
            result, position = {}, 0
            for item in children:
                if item.type != "array_element_initializer":
                    continue
                values = item.named_children
                if len(values) == 1:
                    result[position] = self.expr(values[0], env)
                    position += 1
                elif len(values) == 2:
                    key = self.expr(values[0], env)
                    if not isinstance(key, (str, int)):
                        return Unknown(text)
                    if key in result:
                        return Unknown("Duplicate array key")
                    result[key] = self.expr(values[1], env)
            return result
        if kind == "subscript_expression":
            source, key = self.expr(children[0], env), self.expr(children[1], env) if len(children) > 1 else None
            return source.get(key, None) if isinstance(source, dict) and isinstance(key, (str, int)) else Unknown(text)
        if kind == "class_constant_access_expression":
            enum, member = self.text(children[0]).split("\\")[-1], self.text(children[-1])
            if enum == "SensorType" and member == "State":
                return "state"
            if enum in ("Severity", "SensorState"):
                return {"Ok": 0, "Warning": 1, "Error": 2, "Critical": 2, "Unknown": 3}.get(member, Unknown(text))
            return Unknown(text)
        if kind == "assignment_expression":
            value = bounded(self.expr(node.child_by_field_name("right"), env))
            self.assign(node.child_by_field_name("left"), value, env)
            return value
        if kind == "update_expression":
            argument = node.child_by_field_name("argument")
            value = self.expr(argument, env)
            if type(value) is not int:
                return Unknown(text)
            updated = value + (1 if "++" in text else -1)
            self.assign(argument, updated, env)
            return updated if text.startswith(("++", "--")) else value
        if kind == "binary_expression":
            left_node, right_node = node.child_by_field_name("left"), node.child_by_field_name("right")
            left, right = self.expr(left_node, env), self.expr(right_node, env)
            operator = node.text[left_node.end_byte - node.start_byte:right_node.start_byte - node.start_byte].decode().strip()
            if operator == ".":
                return str(left) + str(right) if known(left) and known(right) else Template([left, right])
            if operator == "??":
                return right if left is None else left
            if known(left) and known(right):
                if operator in ("===", "=="):
                    return type(left) is type(right) and left == right
                if operator in ("!==", "!="):
                    return type(left) is not type(right) or left != right
                if operator in ("&&", "and"):
                    return bool(left and right)
                if operator in ("||", "or"):
                    return bool(left or right)
                if operator in ("+", "-", "*", "/", "<", ">", "<=", ">=") and type(left) in (int, float) and type(right) in (int, float):
                    if operator == "+": return left + right
                    if operator == "-": return left - right
                    if operator == "*": return left * right
                    if operator == "/": return left / right if right else Unknown(text)
                    if operator == "<": return left < right
                    if operator == ">": return left > right
                    if operator == "<=": return left <= right
                    if operator == ">=": return left >= right
            return Unknown(text)
        if kind == "unary_op_expression":
            value = self.expr(children[-1], env)
            if known(value):
                if text.startswith("!"): return not value
                if text.startswith("-") and type(value) is int: return -value
            return Unknown(text)
        if kind == "match_expression":
            value = self.expr(node.child_by_field_name("condition"), env)
            default = None
            for arm in node.child_by_field_name("body").named_children:
                if arm.type == "match_default_expression":
                    default = arm.child_by_field_name("return_expression")
                elif arm.type == "match_conditional_expression":
                    tests = [self.expr(item, env) for item in arm.child_by_field_name("conditional_expressions").named_children]
                    if known(value) and value in tests:
                        return self.expr(arm.child_by_field_name("return_expression"), env)
            return self.expr(default, env) if known(value) and default else Unknown(text)
        if kind == "function_call_expression":
            name, args = self.text(node.child_by_field_name("function")), self.args(node, env)
            if name == "create_state_index" and len(args) >= 2:
                env.setdefault("@states", {})[identity(args[0])] = deepcopy(args[1])
            elif name == "discover_sensor" and len(args) >= 6 and args[1] == "state":
                self.emit(args[5], args[3], env.get("@states", {}).get(identity(args[5])), node, env)
            elif name in ("is_numeric", "is_array", "isset", "empty") and args and known(args[0]):
                if name == "is_numeric": return type(args[0]) in (int, float)
                if name == "is_array": return isinstance(args[0], dict)
                if name == "isset": return args[0] is not None
                return not args[0]
            elif name == "count" and args and isinstance(args[0], dict):
                return len(args[0])
            elif name == "in_array" and len(args) >= 2 and known(args[0]) and isinstance(args[1], dict):
                return args[0] in args[1].values()
            elif name == "base_path" and args and isinstance(args[0], str):
                return args[0]
            elif name in ("strtolower", "trim", "rtrim", "ltrim") and args and isinstance(args[0], str):
                if name == "strtolower": return args[0].lower()
                chars = args[1] if len(args) > 1 and isinstance(args[1], str) else None
                return getattr(args[0], {"trim": "strip", "rtrim": "rstrip", "ltrim": "lstrip"}[name])(chars)
            return Unknown(text)
        if kind in ("include_expression", "require_expression", "include_once_expression", "require_once_expression"):
            path = self.expr(children[0], env) if children else Unknown(text)
            if isinstance(path, str):
                self.includes.append({"path": path, "conditions": deepcopy(env.get("@conditions", []))})
            else:
                self.problems.append({"path": self.path, "line": node.start_point.row + 1, "reason": "Runtime include path"})
            return Unknown(text)
        if kind == "scoped_call_expression":
            scope, name, args = self.text(node.child_by_field_name("scope")).split("\\")[-1], self.text(node.child_by_field_name("name")), self.args(node, env)
            if scope == "StateTranslation" and name == "define" and len(args) >= 3:
                return {"descr": args[0], "value": args[1], "generic": args[2]}
            return Unknown(text)
        if kind == "object_creation_expression" and children and self.text(children[0]).split("\\")[-1] == "Sensor":
            args = self.args(node, env)
            return {"@sensor": args[0]} if args and isinstance(args[0], dict) else Unknown(text)
        if kind == "member_call_expression":
            target = self.expr(node.child_by_field_name("object"), env)
            name, args = self.text(node.child_by_field_name("name")), self.args(node, env)
            if name == "discover" and args and isinstance(args[0], dict):
                return args[0]
            if name == "withStateTranslations" and len(args) >= 2 and isinstance(target, dict) and "@sensor" in target:
                sensor = target["@sensor"]
                if sensor.get("sensor_class") == "state":
                    self.emit(sensor.get("sensor_type"), sensor.get("sensor_oid"), args[1], node, env)
            return Unknown(text)
        if kind == "conditional_expression":
            condition = self.expr(node.child_by_field_name("condition"), env)
            if known(condition):
                return self.expr(node.child_by_field_name("body" if condition else "alternative"), env)
        return Unknown(text)

    def assign(self, node, value, env):
        if node.type == "variable_name":
            # PHP arrays have value semantics (copy on write), unlike Python dicts.
            env[self.text(node)] = deepcopy(value)
        elif node.type == "list_literal":
            for index, child in enumerate(node.named_children):
                self.assign(child, value.get(index, Unknown(self.text(child))) if isinstance(value, dict) else Unknown(self.text(child)), env)
        elif node.type == "subscript_expression":
            children = node.named_children
            target = self.expr(children[0], env)
            if isinstance(target, dict):
                key = self.expr(children[1], env) if len(children) > 1 else max((key for key in target if type(key) is int), default=-1) + 1
                if isinstance(key, (str, int)):
                    target[key] = value

    def emit(self, sensor_type, oid, states, node, env):
        if not isinstance(states, dict) or not states or not known(states):
            self.problems.append({"path": self.path, "line": node.start_point.row + 1, "reason": "Runtime or missing state translations"})
            return
        rows = list(states.values())
        if any(not isinstance(row, dict) for row in rows):
            self.problems.append({"path": self.path, "line": node.start_point.row + 1, "reason": "Unsupported state table shape"})
            return
        self.facts.append({"sensorType": sensor_type, "oid": oid, "states": rows, "path": self.path,
                           "line": node.start_point.row + 1, "context": dict(self.context),
                           "conditions": deepcopy(env.get("@conditions", []))})

    def block(self, node, contexts, depth=0):
        self.step()
        if depth > 64 or len(contexts) > 64:
            raise LimitExceeded("PHP branch/depth limit")
        if node is None:
            return contexts
        kind = node.type
        if kind in ("program", "compound_statement", "declaration_list"):
            for child in node.named_children:
                contexts = self.block(child, contexts, depth + 1)
            return contexts
        if kind == "expression_statement":
            for env in contexts:
                if node.named_children:
                    self.expr(node.named_children[0], env)
            return contexts
        if kind in ("if_statement", "else_if_clause"):
            results = []
            remaining = contexts
            for clause in [node, *node.children_by_field_name("alternative")]:
                following = []
                for env in remaining:
                    condition = self.expr(clause.child_by_field_name("condition"), env) if clause.type != "else_clause" else True
                    if not known(condition) or condition:
                        branch = deepcopy(env)
                        if not known(condition) and (self.routing or "$device" in self.text(clause.child_by_field_name("condition"))):
                            branch.setdefault("@conditions", []).append(self.condition(clause.child_by_field_name("condition"), env))
                        results.extend(self.block(clause.child_by_field_name("body"), [branch], depth + 1))
                    if not known(condition) or not condition:
                        branch = deepcopy(env)
                        if not known(condition) and (self.routing or "$device" in self.text(clause.child_by_field_name("condition"))):
                            branch.setdefault("@conditions", []).append({"not": self.condition(clause.child_by_field_name("condition"), env)})
                        following.append(branch)
                remaining = following
            results.extend(remaining)
            # Deduplicate identical paths early; branches often only change descriptions.
            if not results:
                return []
            joined = {}
            for key in set().union(*(env.keys() for env in results)):
                values = [env.get(key, Unknown("Undefined " + key)) for env in results]
                if key == "@conditions":
                    joined[key] = deepcopy(contexts[0].get(key, []))
                elif key == "@states":
                    states = {}
                    for name in set().union(*(value.keys() for value in values if isinstance(value, dict))):
                        alternatives = [value.get(name, Unknown("Conditional state registration")) if isinstance(value, dict) else Unknown("Conditional state registration") for value in values]
                        states[name] = alternatives[0] if all(repr(value) == repr(alternatives[0]) for value in alternatives) else Unknown("Conditional state registration")
                    joined[key] = states
                else:
                    joined[key] = values[0] if all(repr(value) == repr(values[0]) for value in values) else Unknown("Conditional value " + key)
            return [joined]
        if kind == "else_clause":
            return self.block(node.child_by_field_name("body"), contexts, depth + 1)
        if kind == "for_statement":
            output = []
            for original in contexts:
                env = deepcopy(original)
                self.expr(node.child_by_field_name("initialize"), env)
                for _ in range(1024):
                    condition = self.expr(node.child_by_field_name("condition"), env)
                    if not known(condition):
                        self.problems.append({"path": self.path, "line": node.start_point.row + 1,
                                              "reason": "Runtime for-loop bounds"})
                        break
                    if not condition:
                        output.append(env)
                        break
                    following = self.block(node.child_by_field_name("body"), [env], depth + 1)
                    if not following:
                        # Break/return control flow cannot safely propagate a value.
                        break
                    env = following[0]
                    self.expr(node.child_by_field_name("update"), env)
                else:
                    raise LimitExceeded("PHP static loop size limit")
            return output
        if kind == "switch_statement":
            output = []
            cases = node.child_by_field_name("body").named_children
            for env in contexts:
                value = self.expr(node.child_by_field_name("condition"), env)
                if not known(value):
                    self.problems.append({"path": self.path, "line": node.start_point.row + 1,
                                          "reason": "Runtime switch selector"})
                    continue
                selected, default = None, None
                for index, case in enumerate(cases):
                    if case.type == "default_statement":
                        default = index
                    elif case.type == "case_statement":
                        test = self.expr(case.child_by_field_name("value"), env)
                        # PHP switch uses loose equality. Only compare values whose
                        # numeric/string conversion is unambiguous.
                        equal = type(test) is type(value) and test == value
                        if type(value) is int and isinstance(test, str) and re.fullmatch(r"[+-]?[0-9]+", test):
                            equal = value == int(test)
                        if type(test) is int and isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value):
                            equal = test == int(value)
                        if not known(test):
                            raise ValueError("Runtime switch case")
                        if equal:
                            selected = index
                            break
                selected = default if selected is None else selected
                active = [env]
                stop = False
                for case in cases[selected:] if selected is not None else []:
                    value_node = case.child_by_field_name("value")
                    for statement in case.named_children:
                        if statement == value_node:
                            continue
                        if statement.type == "break_statement":
                            if statement.named_children:
                                raise ValueError("Unsupported multi-level PHP break")
                            stop = True
                            break
                        active = self.block(statement, active, depth + 1)
                    if stop or not active:
                        break
                output.extend(active)
            return output
        if kind == "foreach_statement":
            values = node.named_children
            output = []
            for original in contexts:
                collection = self.expr(values[0], original)
                entries = list(collection.items()) if isinstance(collection, dict) else [(Unknown("index"), Unknown("row"))]
                if len(entries) > 1024:
                    raise LimitExceeded("PHP static loop size limit")
                for key, value in entries:
                    env = deepcopy(original)
                    binding = values[1]
                    if binding.type == "pair":
                        self.assign(binding.named_children[0], key, env)
                        self.assign(binding.named_children[1], value, env)
                    else:
                        self.assign(binding, value, env)
                    self.block(node.child_by_field_name("body"), [env], depth + 1)
                output.append(original)
            return output
        if kind in ("class_declaration", "method_declaration", "function_definition", "namespace_definition"):
            body = node.child_by_field_name("body")
            if body:
                self.block(body, [deepcopy(env) for env in contexts], depth + 1)
            return contexts
        if kind in ("break_statement", "continue_statement", "return_statement"):
            if kind == "return_statement" and node.named_children:
                for env in contexts:
                    self.expr(node.named_children[0], env)
            return []
        if kind == "unset_statement":
            for env in contexts:
                for child in node.named_children:
                    if child.type == "variable_name":
                        env.pop(self.text(child), None)
            return contexts
        if kind in ("php_tag", "comment", "namespace_use_declaration", "echo_statement", "property_declaration"):
            return contexts
        self.problems.append({"path": self.path, "line": node.start_point.row + 1, "reason": "Unsupported PHP statement: " + kind})
        return contexts

    def analyse(self, source):
        if len(source) > 2 * 1024 * 1024:
            raise LimitExceeded("PHP source size limit")
        parser = Parser(Language(tree_sitter_php.language_php()))
        tree = parser.parse(source)
        root = tree.root_node
        if root.has_error or root.descendant_count > 200000:
            raise ValueError("Unsupported PHP syntax or syntax-tree size")
        device = {name: Unknown("$device[" + name + "]") for name in ("os", "os_group", "hardware", "version", "sysObjectID")}
        device.update(self.context)
        self.block(root, [{"$device": device, "@states": {}, "@conditions": []}])
        return self.facts, self.problems
