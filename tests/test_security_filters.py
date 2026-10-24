import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("security_filters", ROOT / "tools/security_filters.py")
filters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(filters)


class SecurityFilterTests(unittest.TestCase):
    def test_only_declared_hashes_in_their_own_files_are_allowed(self):
        pin = json.loads((ROOT / "sources/librenms.json").read_text())["revision"]
        feed = json.loads((ROOT / "feeds/v1/stable.json").read_text())
        digest = feed["shards"][0]["sha256"]
        self.assertTrue(filters.is_catalogue_digest(pin, "sources/librenms.json"))
        self.assertTrue(filters.is_catalogue_digest(digest, "feeds/v1/stable.json"))
        self.assertFalse(filters.is_catalogue_digest(pin, "tools/publish.py"))
        self.assertFalse(filters.is_catalogue_digest("not-a-declared-digest", "feeds/v1/stable.json"))
        self.assertFalse(filters.is_catalogue_digest(digest, "sources/librenms.json"))

    def test_semantic_baseline_only_allows_its_declared_fingerprints(self):
        baseline = json.loads((ROOT / "sources/coverage-baseline.json").read_text())
        digest = next(iter(baseline["definitions"].values()))
        self.assertTrue(filters.is_catalogue_digest(digest, "sources/coverage-baseline.json"))
        self.assertFalse(filters.is_catalogue_digest(digest, "tools/coverage_gate.py"))
        self.assertFalse(filters.is_catalogue_digest("1" * 64, "sources/coverage-baseline.json"))
