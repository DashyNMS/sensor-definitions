import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / ".deps"))
from php_analysis import Analyser, LimitExceeded, OidChoices, Template, Unknown, parent_class


class PhpAnalysisTests(unittest.TestCase):
    def test_aliased_device_metadata_keeps_its_hardware_guard(self):
        source = b"""<?php
$hardware=$this->getDevice()->hardware;
if ($hardware === 'Example') {
 $n='example'; $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']];
 create_state_index($n,$s);
 discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
}
"""
        facts, problems = Analyser(context={'os': 'example'}).analyse(source)
        self.assertEqual([], problems)
        self.assertEqual([{'field': 'hardware', 'op': 'equals', 'value': 'Example'}], facts[0]['conditions'])

    def test_unmodelled_device_fields_do_not_select_a_false_default(self):
        source = b"""<?php
if ($device['unsupported']) { $n='first'; } else { $n='wrong-default'; }
$s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s);
discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
"""
        facts, problems = Analyser().analyse(source)
        self.assertFalse(any(fact['sensorType'] == 'wrong-default' and not fact['conditions'] for fact in facts))

    def test_parent_class_resolution_uses_namespace_and_import_aliases(self):
        self.assertEqual(['LibreNMS\\OS'], parent_class(b'<?php namespace LibreNMS\\OS; use LibreNMS\\OS as BaseOS; class Example extends BaseOS {}'))
        self.assertEqual(['LibreNMS\\OS\\Shared\\Example'], parent_class(b'<?php namespace LibreNMS\\OS; class Example extends Shared\\Example {}'))

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

    def test_early_returns_keep_the_remaining_hardware_condition(self):
        source = b"""<?php
if ($device['hardware'] === 'Excluded') { return; }
$n='example'; $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']];
create_state_index($n,$s);
discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
"""
        facts, problems = Analyser(context={'os': 'example'}).analyse(source)
        self.assertEqual([], problems)
        self.assertEqual([{'not': {'field': 'hardware', 'op': 'equals', 'value': 'Excluded'}}], facts[0]['conditions'])

    def test_foreach_break_cannot_emit_unreachable_later_entries(self):
        source = b"""<?php
foreach (['first','unreachable'] as $n) {
 $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s);
 discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
 break;
}
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual(['first'], [fact['sensorType'] for fact in facts])
        self.assertEqual('Loop control flow requires scope analysis', problems[0]['reason'])

    def test_skipped_unsupported_statements_cannot_leave_stale_state_tables(self):
        source = b"""<?php $n='example';
$s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s);
while (unknown()) { $s=[['value'=>1,'generic'=>2,'descr'=>'Failed']]; create_state_index($n,$s); }
discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual([], facts)
        self.assertTrue(any('while_statement' in item['reason'] for item in problems))

    def test_php_truth_and_uncertain_numeric_coercion_do_not_choose_wrong_states(self):
        source = b"""<?php $n='example';
if ('0') { $s=[['value'=>1,'generic'=>2,'descr'=>'Wrong']]; }
else { $s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; }
create_state_index($n,$s); discover_sensor(null,SensorType::State,$device,'.1.3.6.1.4.1.32473.1',0,$n,'State');
"""
        facts, problems = Analyser().analyse(source)
        self.assertEqual('Ready', facts[0]['states'][0]['descr'])
        self.assertEqual([], problems)
        facts, problems = Analyser().analyse(source.replace(b"if ('0')", b"if ('01' == '1')"))
        self.assertEqual([], facts)
        self.assertTrue(problems)

    def test_unknown_match_only_expands_numeric_oid_alternatives(self):
        source = b"""<?php $n='example';
$oid=match(unknown()) { 'a'=>'.1.3.6.1.4.1.32473.1', 'b'=>'.1.3.6.1.4.1.32473.2', default=>null };
$s=[['value'=>1,'generic'=>0,'descr'=>'Ready']]; create_state_index($n,$s);
discover_sensor(null,SensorType::State,$device,$oid . '.' . $index,0,$n,'State');
"""
        facts, problems = Analyser().analyse(source)
        self.assertIsInstance(facts[0]['oid'].parts[0], OidChoices)
        self.assertEqual([], problems)
