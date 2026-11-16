"""Guard reviewed LibreNMS 26.11.0 changes against accidental reinterpretation."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import catalogue
from coverage_gate import semantic_hash


class ReleaseReviewTests(unittest.TestCase):
    def test_reviewed_mappings_and_omissions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / 'tests/fixtures/librenms-26.11.0',
                            root / 'resources/definitions/os_discovery')
            report = []
            items = catalogue.import_yaml(root, report)
        by_type = {item['match']['sensorType']: item for item in items}
        self.assertEqual([
            {'value': '1', 'label': 'Empty', 'genericState': 'warning'},
            {'value': '2', 'label': 'Power Off', 'genericState': 'critical'},
            {'value': '3', 'label': 'Power On', 'genericState': 'ok'},
        ], by_type['powerRunStatus']['states'])
        self.assertEqual([
            {'value': '1', 'label': 'Alarm', 'genericState': 'critical'},
            {'value': '5', 'label': 'Normal', 'genericState': 'ok'},
        ], by_type['devFanAlarmStatus']['states'])
        self.assertNotIn('alarmCount', by_type)
        self.assertIn('fanMode', by_type)
        self.assertIn('C-Plug', by_type)
        self.assertEqual([1, 2], [entry['entry'] for entry in report])
        self.assertTrue(all(entry['reason'] == 'No explicit sensor type' for entry in report))
        baseline = json.loads((ROOT / 'sources/coverage-baseline.json').read_text())
        for name in ('powerRunStatus', 'devFanAlarmStatus'):
            item = by_type[name]
            self.assertEqual(baseline['definitions'][item['id']], semantic_hash(item))
