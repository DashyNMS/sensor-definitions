import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("catalogue", ROOT / "tools/catalogue.py")
catalogue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalogue)
from php_compiler import compile_sources
from context_rules import definition as rule_definition

FIXTURE = """<?php
$cur_oid = '.1.3.6.1.4.1.32473.1.';
$state_name = 'exampleTemperatureState';
$states = [
 ['value' => 1, 'generic' => 0, 'descr' => 'Normal'],
 ['value' => 2, 'generic' => 2, 'descr' => 'Failed'],
 ['value' => 3, 'generic' => 2, 'descr' => 'Out Of Boundary'],
];
create_state_index($state_name, $states);
foreach ($oids as $index => $entry) {
 discover_sensor(null, SensorType::State, $device, $cur_oid . $index, $index, $state_name, 'Temperature', 1);
}
$cur_oid = '.1.3.6.1.4.1.32473.2.';
$state_name = 'exampleStorageState';
$states = [
 ['value' => 1, 'generic' => 0, 'descr' => 'Normal'],
 ['value' => 2, 'generic' => 2, 'descr' => 'Failed'],
];
create_state_index($state_name, $states);
foreach ($oids as $index => $entry) {
 discover_sensor(null, SensorType::State, $device, $cur_oid . $index, $index, $state_name, 'Storage', 1);
}
"""


class AxisTests(unittest.TestCase):
    def run_import(self, text):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "includes/discovery/sensors/state/axiscam.inc.php"
            file.parent.mkdir(parents=True)
            file.write_text(text)
            detection = root / 'resources/definitions/os_detection/axiscam.yaml'
            detection.parent.mkdir(parents=True)
            detection.write_text('os: axiscam\n')
            report = []
            mappings, rules = compile_sources(root, report, catalogue.definition,
                lambda value: catalogue.yaml.load(value, Loader=catalogue.UniqueLoader))
            for rule in rules:
                try:
                    mapped = rule_definition(rule)
                    if mapped:
                        mappings.append(mapped)
                except ValueError as error:
                    report.append({'path': rule['path'], 'reason': str(error)})
            return mappings, report

    def test_static_tables_preserve_separate_identities_and_severity(self):
        mappings, report = self.run_import(FIXTURE)
        self.assertEqual([], report)
        self.assertEqual(2, len(mappings))
        self.assertEqual("axiscam", mappings[0]["match"]["os"])
        self.assertEqual("1.3.6.1.4.1.32473.1", mappings[0]["match"]["oidPrefix"])
        self.assertEqual("exampleStorageState", mappings[1]["match"]["sensorType"])
        self.assertEqual(["ok", "critical", "critical"], [row["genericState"] for row in mappings[0]["states"]])
        self.assertEqual("Failed", mappings[1]["states"][1]["label"])
        self.assertTrue(mappings[1]["sourceRefs"][0]["suppliesSeverity"])

    def test_dynamic_or_unrelated_discovery_is_not_guessed(self):
        for before, after in [("'generic' => 0", "'generic' => severity()"),
                              ("$cur_oid . $index", "$other_oid . $index"),
                              ("$state_name = 'exampleTemperatureState'", "$state_name = $entry['name']")]:
            mappings, report = self.run_import(FIXTURE.replace(before, after))
            self.assertTrue(report)
            self.assertLess(len(mappings), 2)
