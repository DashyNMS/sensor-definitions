import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_inventory", ROOT / "tools/source_inventory.py")
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class InventoryTests(unittest.TestCase):
    def test_new_php_and_shared_sources_are_accounted_without_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ("includes/discovery/sensors/state/new-vendor.inc.php", "includes/discovery/sensors/shared.inc.php", "LibreNMS/OS/Example.php"):
                file = root / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("<?php create_state_index($name, $states);")
            result = inventory.collect(root, [], [], lambda text: {})
            self.assertEqual(3, result["phpSources"])
            self.assertEqual({"unsupported": 3}, result["totals"])
            self.assertTrue(all(item["reasons"] for item in result["sources"]))

    def test_supported_and_partially_supported_sources_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "includes/discovery/sensors/state/example.inc.php"
            file.parent.mkdir(parents=True)
            file.write_text("<?php")
            path = file.relative_to(root).as_posix()
            mapping = {"sourceRefs": [{"path": path}]}
            result = inventory.collect(root, [mapping], [{"path": path, "reason": "Runtime identity"}], lambda text: {})
            self.assertEqual("partial", result["sources"][0]["status"])
            self.assertEqual(1, result["sources"][0]["mappings"])
