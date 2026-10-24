import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / ".deps")]
import catalogue
import context_rules
from coverage_gate import check, semantic_hash
from promote import feed_updates


class ContextTests(unittest.TestCase):
    def rule(self):
        return {"sensorType": {"parts": ["Input_", {"runtime": "$index", "origin": "snmp-index"}, "_State"]}, "conditions": [
            {"field": "hardware", "op": "contains", "value": "Example"}], "context": {"os": "example-os"},
            "path": "includes/discovery/sensors/state/example.inc.php", "oidPrefix": "1.3.6.1.4.1.32473.1",
            "states": [{"value": "2", "label": "Ready", "genericState": "ok"}]}

    def test_type_templates_and_context_are_data_with_provenance(self):
        item = context_rules.definition(self.rule())
        self.assertEqual("Input_*_State", item["match"]["sensorType"])
        self.assertEqual("template", item["match"]["typeMatch"])
        self.assertEqual("hardware", item["match"]["conditions"][0]["field"])
        example = json.loads((ROOT / 'examples/catalogue-v1.json').read_text())
        example['schemaVersion'] = 2
        example['sources'][0]['id'] = 'librenms'
        example['definitions'] = [item]
        catalogue.validate(example)
        with self.assertRaises(ValueError):
            catalogue.validate(example, production=True)

    def test_dynamic_type_is_bounded_by_os_and_oid_not_guessed_from_values(self):
        rule = self.rule()
        rule['sensorType'] = {'runtime': "$row['objectId']", 'origin': 'snmp-field'}
        item = context_rules.definition(rule)
        self.assertEqual('any', item['match']['typeMatch'])
        self.assertEqual('*', item['match']['sensorType'])
        self.assertEqual(rule['oidPrefix'], item['match']['oidPrefix'])
        self.assertEqual(rule['states'], item['states'])

    def test_unknown_predicates_and_unbounded_templates_fail_closed(self):
        for predicate in ({'unsupported': 'runtime code'}, {'field': 'hardware', 'op': 'regex', 'value': '.*'}):
            rule = self.rule()
            rule['conditions'] = [predicate]
            with self.assertRaises(ValueError):
                context_rules.definition(rule)
        rule = self.rule()
        rule['sensorType'] = {'parts': ['*', {'runtime': 'x'}]}
        with self.assertRaises(ValueError):
            context_rules.definition(rule)
        rule = self.rule(); rule['sensorType'] = {'runtime': 'unrecognised_function()'}
        with self.assertRaises(ValueError):
            context_rules.definition(rule)
        rule = self.rule(); rule['conditions'] = [False]
        self.assertIsNone(context_rules.definition(rule))

    def test_semantic_gate_rejects_loss_state_changes_and_new_unsupported_sources(self):
        item = context_rules.definition(self.rule())
        baseline = {'definitions': {item['id']: semantic_hash(item)}, 'sourceOmissions': {}}
        self.assertEqual(1, check([item], {'sources': []}, baseline)['preservedDefinitions'])
        with self.assertRaisesRegex(ValueError, 'regression'):
            check([], {'sources': []}, baseline)
        changed = copy.deepcopy(item); changed['states'][0]['genericState'] = 'critical'
        with self.assertRaisesRegex(ValueError, 'changed mappings'):
            check([changed], {'sources': []}, baseline)
        with self.assertRaisesRegex(ValueError, 'Unreviewed source omissions'):
            check([item], {'sources': [{'path': 'new.php', 'status': 'unsupported', 'reasons': ['New syntax']}]}, baseline)

    def test_dual_feed_promotion_is_atomic_monotonic_and_compatible(self):
        incoming = {schema: {'schemaVersion': schema, 'catalogueVersion': '26.10.2'} for schema in (1, 2)}
        self.assertEqual(incoming, feed_updates({}, incoming))
        self.assertEqual({}, feed_updates(incoming, incoming))
        wrong = copy.deepcopy(incoming); wrong[2]['catalogueVersion'] = '26.10.3'
        with self.assertRaisesRegex(ValueError, 'together'):
            feed_updates({}, wrong)
        current = copy.deepcopy(incoming); current[2]['catalogueVersion'] = '26.10.3'
        with self.assertRaisesRegex(ValueError, 'downgrade'):
            feed_updates(current, incoming)
