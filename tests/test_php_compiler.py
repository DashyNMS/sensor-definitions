from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / ".deps")]
import catalogue
from php_compiler import compile_sources


class CompilerTests(unittest.TestCase):
    def test_a_new_filename_and_os_are_automatically_compiled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            detection = root / "resources/definitions/os_detection/new-example.yaml"
            detection.parent.mkdir(parents=True)
            detection.write_text("os: new-example\n")
            source = root / "includes/discovery/sensors/state/new-example.inc.php"
            source.parent.mkdir(parents=True)
            source.write_text("""<?php
$state_name = 'exampleFan';
$states = [['value'=>1,'generic'=>0,'descr'=>'Ready']];
create_state_index($state_name,$states);
discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1.' . $index,$index,$state_name,'Fan');
""")
            report = []
            definitions, rules = compile_sources(root, report, catalogue.definition, lambda text: catalogue.yaml.load(text, Loader=catalogue.UniqueLoader))
            self.assertEqual([], report)
            self.assertEqual([], rules)
            self.assertEqual(1, len(definitions))
            self.assertEqual("new-example", definitions[0]["match"]["os"])
            self.assertEqual("Ready", definitions[0]["states"][0]["label"])

    def test_hardware_routing_is_preserved_as_a_rule_not_applied_globally(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            detection = root / "resources/definitions/os_detection/example.yaml"
            detection.parent.mkdir(parents=True)
            detection.write_text("os: example\n")
            router = root / "includes/discovery/sensors.inc.php"
            router.parent.mkdir(parents=True)
            router.write_text("<?php if (isset($device['hardware']) && strstr($device['hardware'], 'Example')) { include base_path('includes/discovery/sensors/state/shared.inc.php'); }")
            source = root / "includes/discovery/sensors/state/shared.inc.php"
            source.parent.mkdir(parents=True)
            source.write_text("<?php $n='exampleFan'; $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s); discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'Fan');")
            report = []
            definitions, rules = compile_sources(root, report, catalogue.definition, lambda text: catalogue.yaml.load(text, Loader=catalogue.UniqueLoader))
            self.assertEqual([], definitions)
            self.assertEqual(1, len(rules))
            self.assertEqual("all", next(iter(rules[0]["conditions"][0])))

    def test_device_conditions_inside_a_module_are_preserved(self):
        from php_analysis import Analyser
        facts, problems = Analyser(context={"os": "example"}).analyse(b"""<?php
if ($device['hardware'] === 'Example chassis') {
 $n='example'; $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']];
 create_state_index($n,$s);
 discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
}
""")
        self.assertEqual([], problems)
        self.assertEqual([{"field": "hardware", "op": "equals", "value": "Example chassis"}], facts[0]["conditions"])
