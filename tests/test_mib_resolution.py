from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / ".deps")]
from mib_resolution import MibResolver
import catalogue


BASE = '''EXAMPLE-ROOT DEFINITIONS ::= BEGIN
example OBJECT IDENTIFIER ::= { iso 3 6 1 4 1 32473 }
END
'''
CHILD = '''EXAMPLE-MIB DEFINITIONS ::= BEGIN
IMPORTS example FROM EXAMPLE-ROOT;
exampleState OBJECT IDENTIFIER ::= { example 7 }
exampleReading OBJECT-TYPE
 SYNTAX INTEGER { ready(1), failed(2) }
 MAX-ACCESS read-only
 STATUS current
 DESCRIPTION "Fixture only; enum labels do not establish severity."
 ::= { exampleState 3 }
END
'''


class MibTests(unittest.TestCase):
    def fixture(self, root):
        directory = root / 'mibs/example'
        directory.mkdir(parents=True)
        (directory / 'root').write_text(BASE)
        (directory / 'child').write_text(CHILD)

    def test_module_imports_and_cached_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            resolver = MibResolver(root)
            for _ in range(2):
                resolver.used.clear()
                self.assertEqual('1.3.6.1.4.1.32473.7.0', resolver.oid('EXAMPLE-MIB::exampleState.0'))
                self.assertEqual({'mibs/example/root', 'mibs/example/child'}, resolver.used)
            self.assertEqual('1.3.6.1.4.1.32473.7.3', resolver.oid('EXAMPLE-MIB::exampleReading'))

    def test_ambiguous_modules_missing_symbols_and_cycles_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            resolver = MibResolver(root)
            with self.assertRaisesRegex(ValueError, 'Missing official MIB symbol'):
                resolver.oid('EXAMPLE-MIB::absent')
            (root / 'mibs/example/other').write_text(CHILD.replace('{ example 7 }', '{ example 8 }'))
            with self.assertRaisesRegex(ValueError, 'Ambiguous official MIB module'):
                MibResolver(root).oid('EXAMPLE-MIB::exampleState')
            (root / 'mibs/example/other').unlink()
            (root / 'mibs/example/child').write_text(CHILD.replace('{ example 7 }', '{ exampleState 7 }'))
            with self.assertRaisesRegex(ValueError, 'Cyclic'):
                MibResolver(root).oid('EXAMPLE-MIB::exampleState')

    def test_yaml_fallback_uses_oid_for_type_and_value_for_numeric_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            directory = root / 'resources/definitions/os_discovery'
            directory.mkdir(parents=True)
            (directory / 'example.yaml').write_text('''modules:
  sensors:
    state:
      data:
        - oid: EXAMPLE-MIB::exampleTable
          value: EXAMPLE-MIB::exampleState
          states:
            - {value: 1, descr: Ready, generic: 0}
        - state_name: explicit
          oid: EXAMPLE-MIB::exampleState
          num_oid: '.1.3.6.1.4.1.32473.9.{{ $index }}'
          states:
            - {value: 2, descr: Failed, generic: 2}
''')
            report = []
            result = catalogue.import_yaml(root, report)
            self.assertEqual([], report)
            self.assertEqual('EXAMPLE-MIB::exampleTable', result[0]['match']['sensorType'])
            self.assertEqual('1.3.6.1.4.1.32473.7', result[0]['match']['oidPrefix'])
            self.assertEqual(3, len(result[0]['sourceRefs']))
            self.assertEqual([False, False], [ref['suppliesSeverity'] for ref in result[0]['sourceRefs'][1:]])
            self.assertEqual('explicit', result[1]['match']['sensorType'])
            self.assertEqual('1.3.6.1.4.1.32473.9', result[1]['match']['oidPrefix'])

    def test_no_name_guessing_or_mib_severity_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            resolver = MibResolver(root)
            for identity in ('exampleState', '../EXAMPLE-MIB::exampleState', 'EXAMPLE-MIB::exampleState.{{ $index }}'):
                with self.assertRaises(ValueError):
                    resolver.oid(identity)
