"""Nightly skip decisions depend on tags at HEAD, not tag timestamps."""
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('catalogue_build_version', TOOLS / 'build_version.py')
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


class NightlyVersionTests(unittest.TestCase):
    def test_schedule_skips_existing_head_tag_and_manual_run_still_builds(self):
        def git(*args):
            if args == ('rev-parse', 'HEAD'):
                return 'a' * 40
            if '--points-at' in args:
                return 'v26.10.2-nightly.2'
            return 'v26.10.2-nightly.1'
        with tempfile.TemporaryDirectory() as folder:
            for event, expected in [('schedule', 'false'), ('workflow_dispatch', 'true')]:
                output = io.StringIO()
                with patch.dict(os.environ, {'GITHUB_EVENT_NAME': event, 'GITHUB_RUN_NUMBER': '3'}, clear=True), \
                        patch.object(version, 'git', side_effect=git), \
                        patch.object(Path, 'read_text', side_effect=['{"release": "26.10.2"}', '## Fixed\n\n- Synthetic change.\n']), \
                        patch('sys.argv', ['build_version', 'nightly', '--notes', str(Path(folder) / 'notes.md')]), \
                        patch('sys.stdout', output):
                    version.main()
                self.assertIn('changed=' + expected, output.getvalue())
