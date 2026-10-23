import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("catalogue", ROOT / "tools/catalogue.py")
catalogue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalogue)


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((ROOT / "examples/catalogue-v1.json").read_text())

    def test_schema_and_production_provenance(self):
        catalogue.validate(self.example)
        with self.assertRaises(ValueError):
            catalogue.validate(self.example, production=True)

    def test_ambiguous_matches_and_duplicate_values_reject(self):
        self.example["definitions"].append(copy.deepcopy(self.example["definitions"][0]))
        with self.assertRaises(ValueError):
            catalogue.validate(self.example)
        self.example["definitions"].pop()
        self.example["definitions"][0]["states"].append(self.example["definitions"][0]["states"][0])
        with self.assertRaises(ValueError):
            catalogue.validate(self.example)

    def test_literal_oid_and_php_expressions(self):
        self.assertEqual("1.3.6.1.4.1.32473.1", catalogue.oid_prefix(".1.3.6.1.4.1.32473.1.{{ $index }}"))
        for value in (".1.3.{{ $index }}.4", "{{ $oid }}", "1.02.3"):
            with self.assertRaises(ValueError):
                catalogue.oid_prefix(value)
        self.assertEqual({"value": 1, "descr": "ready", "generic": 0}, catalogue.php_literal_row("'value' => 1, 'descr' => 'ready', 'generic' => 0"))
        with self.assertRaises(ValueError):
            catalogue.php_literal_row("'value' => system('anything')")

    def test_yaml_state_name_and_generic_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "resources/definitions/os_discovery"
            directory.mkdir(parents=True)
            (directory / "example-os.yaml").write_text("""modules:
  sensors:
    state:
      data:
        - state_name: exampleFanState
          num_oid: '.1.3.6.1.4.1.32473.1.{{ $index }}'
          states:
            - {value: 2, descr: ready, generic: 0}
        - state_name: dynamic
          num_oid: '{{ $oid }}'
          states:
            - {value: 1, descr: unknown, generic: 3}
""")
            report = []
            result = catalogue.import_yaml(root, report)
            self.assertEqual(1, len(result))
            self.assertEqual("exampleFanState", result[0]["match"]["sensorType"])
            self.assertEqual({"value": "2", "label": "ready", "genericState": "ok"}, result[0]["states"][0])
            self.assertEqual(1, len(report))

    def test_php_match_import_uses_explicit_group_membership(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            php = root / "includes/discovery/sensors/state"
            php.mkdir(parents=True)
            (php / "cisco.inc.php").write_text("""<?php
$tables = [
 ['num_oid' => '.1.3.6.1.4.1.32473.1.', 'state_name' => 'exampleFanState'],
];
$states = match ($state_name) {
 'exampleFanState' => [
  ['value' => 2, 'generic' => 0, 'descr' => 'ready'],
 ],
};
""")
            os_dir = root / "resources/definitions/os_detection"
            os_dir.mkdir(parents=True)
            (os_dir / "example.yaml").write_text("os: example-os\ngroup: cisco\n")
            (os_dir / "other.yaml").write_text("os: unrelated\ngroup: other\n")
            result = catalogue.import_cisco(root, [])
            self.assertEqual(1, len(result))
            self.assertEqual("example-os", result[0]["match"]["os"])
            file = php / "cisco.inc.php"
            original = file.read_text()
            file.write_text(original.replace("'exampleFanState' => [", "'otherFanState', 'exampleFanState' => ["))
            self.assertEqual(1, len(catalogue.import_cisco(root, [])))
            file.write_text(original.replace("'exampleFanState' => [", "'exampleFanState'" + " " * 10000 + "invalid ["))
            report = []
            self.assertEqual([], catalogue.import_cisco(root, report))
            self.assertTrue(report)

    def test_deterministic_encoding(self):
        self.assertEqual(catalogue.encode(self.example), catalogue.encode(copy.deepcopy(self.example)))

    def test_yaml_rejects_object_construction_and_duplicate_keys(self):
        with self.assertRaises(catalogue.yaml.constructor.ConstructorError):
            catalogue.yaml.load('!!python/object/apply:os.system ["never-run"]', Loader=catalogue.UniqueLoader)
        with self.assertRaisesRegex(ValueError, "Duplicate YAML key"):
            catalogue.yaml.load("value: 1\nvalue: 2\n", Loader=catalogue.UniqueLoader)

    def test_plain_state_labels_are_not_yaml_booleans(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "resources/definitions/os_discovery"
            directory.mkdir(parents=True)
            (directory / "example-os.yaml").write_text("""modules:
  sensors:
    state:
      data:
        - state_name: exampleFanState
          num_oid: '.1.3.6.1.4.1.32473.1.{{ $index }}'
          states:
            - {value: 1, descr: off, generic: 3}
            - {value: 2, descr: on, generic: 0}
            - {value: 3, descr: yes, generic: 0}
            - {value: 4, descr: no, generic: 1}
""")
            report = []
            result = catalogue.import_yaml(root, report)
            self.assertEqual([], report)
            self.assertEqual(["off", "on", "yes", "no"], [row["label"] for row in result[0]["states"]])
            flags = catalogue.yaml.load("enabled: true\ndisabled: false\n", Loader=catalogue.UniqueLoader)
            self.assertIs(flags["enabled"], True)
            self.assertIs(flags["disabled"], False)
            # Do not change the global loader used by other code.
            self.assertIs(catalogue.yaml.safe_load("off"), False)


if __name__ == "__main__":
    unittest.main()
