from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / ".deps")]
import catalogue
from php_compiler import compile_sources, routes, safe_source, oid_identity, oid_options
from php_analysis import Template, Unknown, OidChoices


class CompilerTests(unittest.TestCase):
    def test_inherited_os_discovery_is_routed_from_declared_parent_classes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            detection = root / 'resources/definitions/os_detection/new-example.yaml'
            detection.parent.mkdir(parents=True)
            detection.write_text('os: new-example\n')
            modern = root / 'LibreNMS/OS/NewExample.php'
            modern.parent.mkdir(parents=True)
            modern.write_text('<?php namespace LibreNMS\\OS; class NewExample extends Shared\\Example {}')
            parent = root / 'LibreNMS/OS/Shared/Example.php'
            parent.parent.mkdir(parents=True)
            parent.write_text("<?php namespace LibreNMS\\OS\\Shared; use LibreNMS\\OS as BaseOS; class Example extends BaseOS { public function discoverState() { $n='exampleFan'; $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s); discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'Fan'); } }")
            (root / 'LibreNMS/OS.php').write_text('<?php namespace LibreNMS; class OS {}')
            report = []
            mappings, rules = compile_sources(root, report, catalogue.definition, lambda value: catalogue.yaml.load(value, Loader=catalogue.UniqueLoader))
            self.assertEqual([], report)
            self.assertEqual([], rules)
            self.assertEqual(1, len(mappings))
            self.assertEqual('new-example', mappings[0]['match']['os'])
            self.assertEqual('LibreNMS/OS/Shared/Example.php', mappings[0]['sourceRefs'][0]['path'])

    def test_shared_group_routes_do_not_apply_to_other_operating_systems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            detection = root / 'resources/definitions/os_detection'
            detection.mkdir(parents=True)
            (detection / 'example.yaml').write_text('os: example\ngroup: example-shared\n')
            (detection / 'other.yaml').write_text('os: other\ngroup: other-group\n')
            source = root / 'includes/discovery/sensors/state/example-shared.inc.php'
            source.parent.mkdir(parents=True)
            source.write_text("<?php $n='exampleFan'; $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s); discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'Fan');")
            report = []
            mappings, rules = compile_sources(root, report, catalogue.definition, lambda value: catalogue.yaml.load(value, Loader=catalogue.UniqueLoader))
            self.assertEqual([], report)
            self.assertEqual([], rules)
            self.assertEqual(['example'], [mapping['match']['os'] for mapping in mappings])

    def test_oid_alternatives_and_fixed_suffixes_preserve_component_identity(self):
        options = oid_options(Template([OidChoices(['.1.3.6.1.4.1.32473.1', '.1.3.6.1.4.1.32473.2']), '.', Unknown('index'), '.6.1']))
        self.assertEqual([('1.3.6.1.4.1.32473.1', '6.1'), ('1.3.6.1.4.1.32473.2', '6.1')], [oid_identity(option) for option in options])
        with self.assertRaises(ValueError):
            oid_identity(Template(['.1.3.6.1.4.1.32473.', Unknown('index'), '.6.', Unknown('other')]))

    def test_official_style_group_names_with_spaces_and_unsafe_include_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            detection = root / 'resources/definitions/os_detection/example.yaml'
            detection.parent.mkdir(parents=True)
            detection.write_text('os: example\ngroup: EXAMPLE GROUP\n')
            self.assertEqual([], routes(root, lambda text: catalogue.yaml.load(text, Loader=catalogue.UniqueLoader)))
            for path in ('../outside.php', '/outside.php', 'C:/outside.php', r'..\outside.php'):
                with self.assertRaises(ValueError):
                    safe_source(root, path)

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

    def test_new_included_modules_are_followed_without_filename_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            detection = root / 'resources/definitions/os_detection/example.yaml'
            detection.parent.mkdir(parents=True)
            detection.write_text('os: example\n')
            parent = root / 'includes/discovery/sensors/state/example.inc.php'
            parent.parent.mkdir(parents=True)
            parent.write_text("<?php include base_path('includes/discovery/sensors/new-shared.inc.php');")
            child = root / 'includes/discovery/sensors/new-shared.inc.php'
            child.write_text("<?php $n='exampleFan'; $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s); discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'Fan');")
            report = []
            definitions, rules = compile_sources(root, report, catalogue.definition, lambda text: catalogue.yaml.load(text, Loader=catalogue.UniqueLoader))
            self.assertEqual([], report)
            self.assertEqual([], rules)
            self.assertEqual(1, len(definitions))
            self.assertEqual('includes/discovery/sensors/new-shared.inc.php', definitions[0]['sourceRefs'][0]['path'])
