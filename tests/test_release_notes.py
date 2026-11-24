import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import release_notes  # noqa: E402

CHANGES = "Intro.\n\n## Fixed\n\n- **Fans.** Named again (#1).\n"


class ReleaseNotesTests(unittest.TestCase):
    def test_the_committed_notes_are_valid(self):
        release_notes.pending((TOOLS.parent / release_notes.NEXT).read_text(encoding="utf-8"))

    def test_a_catalogue_with_no_changes_of_ours_has_only_its_summary(self):
        self.assertEqual("summary\n", release_notes.with_notes(release_notes.BLANK, "summary\n"))

    def test_changes_come_before_the_summary_without_the_instructions(self):
        text = release_notes.with_notes(CHANGES, "summary\n")
        self.assertTrue(text.startswith("## Fixed\n\n- **Fans.**"))
        self.assertTrue(text.endswith("---\n\nsummary\n"))

    def test_mistakes_are_refused(self):
        for text in ("## Improved\n\n- No.\n", "- Loose.\n", "## New\n", "## New\n\n## Fixed\n\n- One.\n", "- Loose.\n## New\n\n- One.\n"):
            with self.assertRaises(ValueError):
                release_notes.pending(text)

    def test_the_instructions_are_never_published(self):
        text = release_notes.with_notes(release_notes.BLANK + "\n## Fixed\n\n- **Fans.** Named again (#1).\n", "summary\n")
        self.assertEqual("## Fixed\n\n- **Fans.** Named again (#1).\n\n---\n\nsummary\n", text)

    def archive(self, now, published):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / release_notes.NEXT
        path.parent.mkdir(parents=True)
        path.write_text(now, encoding="utf-8", newline="\n")
        done = release_notes.archive(folder.name, "26.12.0", published)
        kept = path.parent / "26.12.0.md"
        return done, kept.read_text(encoding="utf-8") if kept.exists() else None, path.read_text(encoding="utf-8")

    def test_published_notes_take_their_version_and_the_next_start_blank(self):
        self.assertEqual((True, "## Fixed\n\n- **Fans.** Named again (#1).\n", release_notes.BLANK), self.archive(CHANGES, CHANGES))

    def test_a_change_added_after_publishing_waits_for_the_next_catalogue(self):
        later = CHANGES + "- **Doors.** Named too (#2).\n\n## New\n\n- **Pumps.** Added (#3).\n"
        done, kept, left = self.archive(later, CHANGES)
        self.assertTrue(done)
        self.assertNotIn("Doors", kept)
        self.assertNotIn("Fans", left)
        self.assertIn("## New\n\n- **Pumps.**", left)
        self.assertIn("## Fixed\n\n- **Doors.**", left)
        release_notes.pending(left)

    def test_nothing_is_kept_for_a_catalogue_with_no_changes_of_ours(self):
        self.assertEqual((False, None, CHANGES), self.archive(CHANGES, release_notes.BLANK))


class BuildVersionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "sources").mkdir()
        (self.root / "docs/releases").mkdir(parents=True)
        (self.root / "sources/librenms.json").write_text(json.dumps({"release": "26.11.0"}))
        (self.root / release_notes.NEXT).write_text(CHANGES, encoding="utf-8", newline="\n")
        self.git("init", "--quiet", "-b", "main")
        self.commit("first")

    def git(self, *args):
        subprocess.run(("git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args),
                       cwd=self.root, check=True, capture_output=True)

    def commit(self, text):
        (self.root / "file").write_text(text)
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", text)

    def build(self, channel, event="push"):
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_OUTPUT"}
        env.update(GITHUB_RUN_NUMBER="3", GITHUB_EVENT_NAME=event, GITHUB_REPOSITORY="DashyNMS/example")
        done = subprocess.run((sys.executable, str(TOOLS / "build_version.py"), channel, "--notes", "out/notes.md"),
                              cwd=self.root, env=env, capture_output=True, text=True, check=True)
        self.text = (self.root / "out/notes.md").read_text(encoding="utf-8")
        return dict(line.split("=", 1) for line in done.stdout.splitlines())

    def test_builds_are_named_for_the_pinned_release(self):
        self.assertEqual("v26.11.0-edge.3", self.build("edge")["tag"])
        self.assertNotIn("Fans", self.text)
        self.assertEqual("26.11.0-nightly.3", self.build("nightly")["version"])
        self.assertIn("Fans", self.text)

    def test_the_schedule_skips_a_commit_that_already_has_a_nightly(self):
        self.git("tag", "v26.11.0-nightly.1")
        self.git("tag", "v26.11.0-edge.2")
        self.assertEqual("false", self.build("nightly", "schedule")["changed"])
        self.assertEqual("true", self.build("nightly", "workflow_dispatch")["changed"])
        self.commit("later")
        self.assertEqual("true", self.build("nightly", "schedule")["changed"])
        self.assertIn("compare/v26.11.0-nightly.1...v26.11.0-nightly.3", self.text)
        self.build("edge")
        self.assertIn("compare/v26.11.0-edge.2...v26.11.0-edge.3", self.text)


if __name__ == "__main__":
    unittest.main()
