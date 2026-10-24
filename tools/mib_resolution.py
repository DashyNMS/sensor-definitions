"""Resolve numeric OIDs from pinned SMI syntax trees, never generated code."""
from collections import defaultdict
import hashlib
from pathlib import Path
import re

from pysmi.error import PySmiError
from pysmi.parser.dialect import smi_v1_relaxed
from pysmi.parser.smi import parserFactory


class MibResolver:
    def __init__(self, upstream):
        self.upstream = Path(upstream)
        self.files = defaultdict(list)
        self.modules = {}
        self.cache = {}
        self.used = set()
        self.parser = parserFactory(**smi_v1_relaxed)()
        header = re.compile(rb"(?m)^[ \t]*([A-Za-z][A-Za-z0-9-]*)\s+DEFINITIONS\s*::=\s*BEGIN")
        for file in sorted((self.upstream / "mibs").rglob("*")):
            if file.is_file():
                with file.open("rb") as stream:
                    match = header.search(stream.read(65536))
                if match:
                    self.files[match[1].decode("ascii")].append(file)

    def module(self, name):
        if name in self.modules:
            return self.modules[name]
        files = self.files.get(name, [])
        if not files:
            raise ValueError("Missing official MIB module: " + name)
        content = {}
        for file in files:
            if file.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("MIB module size limit: " + name)
            raw = file.read_bytes()
            content.setdefault(hashlib.sha256(raw).digest(), (file, raw))
        if len(content) != 1:
            raise ValueError("Ambiguous official MIB module: " + name)
        file, raw = next(iter(content.values()))
        try:
            parsed = self.parser.parse(raw.decode("utf-8"))
        except (PySmiError, UnicodeError, RecursionError) as error:
            raise ValueError("Unsupported official MIB syntax: " + name) from error
        matches = [module for module in parsed if module[0] == name]
        if len(matches) != 1:
            raise ValueError("MIB module identity mismatch: " + name)
        _, _, imports, declarations = matches[0]
        if len(declarations or []) > 20000:
            raise ValueError("MIB declaration count limit")
        symbols = {}
        for declaration in declarations or []:
            if declaration and isinstance(declaration[-1], tuple) and declaration[-1][0] == "objectIdentifier":
                symbol = declaration[1]
                if symbol in symbols:
                    raise ValueError("Duplicate MIB symbol: " + name + "::" + symbol)
                symbols[symbol] = declaration[-1][1]
        imported = {}
        for module, names in imports.items():
            for symbol in names:
                if symbol in imported and imported[symbol] != module:
                    raise ValueError("Ambiguous imported MIB symbol")
                imported[symbol] = module
        self.modules[name] = (symbols, imported, file.relative_to(self.upstream).as_posix())
        return self.modules[name]

    def resolve(self, module, symbol, trail=()):
        key = (module, symbol)
        if key in self.cache:
            value, paths = self.cache[key]
            self.used.update(paths)
            return value
        if key in trail or len(trail) > 128:
            raise ValueError("Cyclic or excessive MIB OID dependency")
        if symbol in ("iso", "ccitt", "joint-iso-ccitt"):
            return {"iso": (1,), "ccitt": (0,), "joint-iso-ccitt": (2,)}[symbol]
        symbols, imports, path = self.module(module)
        self.used.add(path)
        if symbol not in symbols:
            if symbol in imports:
                target = (imports[symbol], symbol)
                result = self.resolve(*target, trail + (key,))
                paths = self.cache.get(target, (None, set()))[1] | {path}
                self.cache[key] = (result, paths)
                self.used.update(paths)
                return result
            raise ValueError("Missing official MIB symbol: " + module + "::" + symbol)
        components = symbols[symbol]
        if not components or len(components) > 128:
            raise ValueError("Unsupported MIB OID shape")
        result = ()
        paths = {path}
        for component in components:
            if type(component) is int:
                result += (component,)
            elif isinstance(component, tuple) and len(component) == 2 and type(component[1]) is int:
                result += (component[1],)
            elif isinstance(component, str):
                target = (imports.get(component, module), component)
                parent = self.resolve(*target, trail + (key,))
                paths.update(self.cache.get(target, (None, set()))[1])
                if result and parent[:len(result)] != result:
                    raise ValueError("Inconsistent named MIB OID prefix")
                result = parent
            else:
                raise ValueError("Unsupported MIB OID component")
        if not result or len(result) > 128 or any(number < 0 or number > 4294967295 for number in result):
            raise ValueError("Invalid MIB OID components")
        self.cache[key] = (result, paths)
        return result

    def oid(self, qualified):
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9-]*)::([A-Za-z][A-Za-z0-9-]*)(\.[0-9]+)*", qualified or "")
        if not match:
            raise ValueError("No qualified MIB OID identity")
        module, symbol = match[1], match[2]
        suffix = qualified[len(module) + len(symbol) + 2:]
        value = self.resolve(module, symbol)
        return ".".join(str(number) for number in value) + suffix
