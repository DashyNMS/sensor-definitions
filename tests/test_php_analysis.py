import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / ".deps"))
from php_analysis import Analyser, LimitExceeded, Template, Unknown


class PhpAnalysisTests(unittest.TestCase):
    def test_nested_tables_destructuring_and_unknown_snmp_rows(self):
        source = b"""<?php
$tables = [['exampleFan', '.1.3.6.1.4.1.32473.1.', [['value'=>1,'generic'=>0,'descr'=>'Ready']]]];
foreach ($tables as $table) {
 [$name, $oid, $states] = $table;
 $rows = snmpwalk_cache_oid($device, 'example', [], 'EXAMPLE-MIB');
 if (!empty($rows)) {
  create_state_index($name, $states);
  foreach ($rows as $index => $row) { discover_sensor(null, SensorType::State, $device, $oid . $index, $index, $name, 'Fan'); }
 }
}
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual(1, len(facts))
        self.assertEqual("exampleFan", facts[0]["sensorType"])
        self.assertIsInstance(facts[0]["oid"], Template)
        self.assertEqual(0, facts[0]["states"][0]["generic"])
        self.assertEqual([], problems)

    def test_match_defaults_and_aliases_are_selected_from_static_name(self):
        source = b"""<?php
$name = 'exampleFan';
$states = match ($name) {
 'other', 'unused' => [['value'=>1,'generic'=>2,'descr'=>'Failed']],
 default => [['value'=>1,'generic'=>0,'descr'=>'Ready']],
};
create_state_index($name,$states);
discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1.0',0,$name,'Fan');
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual("Ready", facts[0]["states"][0]["descr"])
        self.assertEqual([], problems)

    def test_modern_fluent_sensor_registration_is_extracted(self):
        source = b"""<?php
app('sensor-discovery')->discover(new Sensor([
 'sensor_class'=>'state','sensor_type'=>'exampleState','sensor_oid'=>'.1.3.6.1.4.1.32473.1.0'
]))->withStateTranslations('exampleState', [StateTranslation::define('Ready',1,Severity::Ok),StateTranslation::define('Failed',2,Severity::Error)]);
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual(1, len(facts))
        self.assertEqual([0, 2], [row["generic"] for row in facts[0]["states"]])
        self.assertEqual([], problems)

    def test_unknown_calls_and_dynamic_labels_are_not_executed_or_guessed(self):
        source = b"""<?php
$name='example'; $states=[['value'=>1,'generic'=>0,'descr'=>system('never execute')]];
create_state_index($name,$states); discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$name,'State');
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual([], facts)
        self.assertTrue(problems)

    def test_resource_limits_and_invalid_php_fail_closed(self):
        with self.assertRaises(LimitExceeded):
            Analyser().analyse(b" " * (2 * 1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            Analyser().analyse(b"<?php $states = [;")

    def test_bounded_for_switch_and_fallthrough(self):
        source = b"""<?php
for ($i=0; $i<3; $i++) {
 switch ($i) {
  case '0': $name='first'; break;
  case 1:
  case 2: $name='later'; break;
  default: $name='wrong';
 }
 $states=[['value'=>010,'generic'=>0,'descr'=>'Ready']];
 create_state_index($name,$states);
 discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$name,'State');
}
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual(['first', 'later', 'later'], [fact['sensorType'] for fact in facts])
        self.assertEqual(8, facts[0]['states'][0]['value'])
        self.assertEqual([], problems)

    def test_unbounded_for_and_runtime_switch_fail_closed(self):
        with self.assertRaises(LimitExceeded):
            Analyser().analyse(b'<?php for($i=0;true;$i++) { $x=1; }')
        facts, problems = Analyser().analyse(b'<?php switch(snmp_get()) { case 1: $x=1; break; }')
        self.assertEqual([], facts)
        self.assertEqual('Runtime switch selector', problems[0]['reason'])

    def test_exponential_values_are_bounded_before_memory_growth(self):
        with self.assertRaises(LimitExceeded):
            Analyser().analyse(b'<?php $s="x"; for($i=0;$i<100;$i++) { $s=$s.$s; }')

    def test_conditional_state_assignments_are_not_joined_as_one_table(self):
        source = b"""<?php $n='example';
if (snmp_get()) { $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; }
else { $s=[['value'=>1,'generic'=>2,'descr'=>'Failed']]; }
create_state_index($n,$s);
discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual([], facts)
        self.assertEqual('Runtime or missing state translations', problems[0]['reason'])

    def test_array_aliases_and_registered_states_keep_value_semantics(self):
        source = b"""<?php $n='example';
$s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; $copy=$s;
$copy[0]['descr']='Changed copy'; create_state_index($n,$s);
$s[0]['descr']='Changed after registration';
discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual('Ready', facts[0]['states'][0]['descr'])
        self.assertEqual([], problems)
