import base64
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


upstream = load("upstream_release")
promote = load("promote")


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.responses = {
            "repos/librenms/librenms/releases/latest": {"tag_name": "26.10.2", "draft": False, "prerelease": False},
            "repos/librenms/librenms/git/ref/tags/26.10.2": {"object": {"type": "commit", "sha": self.sha}},
            "repos/example/catalogue/contents/feeds/v1/stable.json?ref=main": {
                "content": base64.b64encode(json.dumps({"catalogueVersion": "1.0.1"}).encode()).decode()},
        }

    def fetch(self, endpoint):
        if endpoint not in self.responses:
            raise upstream.NotFound(endpoint)
        return self.responses[endpoint]

    def test_new_release_builds_from_exact_commit(self):
        self.assertEqual({"version": "26.10.2", "revision": self.sha, "action": "build"}, upstream.release_plan("example/catalogue", fetch=self.fetch))

    def test_annotated_tags_are_peeled(self):
        self.responses["repos/librenms/librenms/git/ref/tags/26.10.2"] = {"object": {"type": "tag", "sha": "b" * 40}}
        self.responses["repos/librenms/librenms/git/tags/" + "b" * 40] = {"object": {"type": "commit", "sha": self.sha}}
        self.assertEqual(self.sha, upstream.release_plan("example/catalogue", fetch=self.fetch)["revision"])

    def test_published_release_retries_feed_promotion(self):
        self.responses["repos/example/catalogue/releases/tags/v26.10.2"] = {"tag_name": "v26.10.2"}
        self.assertEqual("promote", upstream.release_plan("example/catalogue", fetch=self.fetch)["action"])

    def test_already_active_release_is_a_noop(self):
        self.responses["repos/example/catalogue/contents/feeds/v1/stable.json?ref=main"]["content"] = base64.b64encode(b'{"catalogueVersion":"26.10.2"}').decode()
        self.assertIsNone(upstream.release_plan("example/catalogue", fetch=self.fetch))

    def test_partial_publication_never_overwrites_a_tag(self):
        self.responses["repos/example/catalogue/git/ref/tags/v26.10.2"] = {"object": {"type": "commit", "sha": self.sha}}
        with self.assertRaisesRegex(ValueError, "incomplete publication"):
            upstream.release_plan("example/catalogue", fetch=self.fetch)

    def test_official_release_does_not_replace_its_catalogue_correction(self):
        self.responses["repos/example/catalogue/contents/feeds/v1/stable.json?ref=main"]["content"] = base64.b64encode(b'{"catalogueVersion":"26.10.2+catalogue.1"}').decode()
        self.assertIsNone(upstream.release_plan("example/catalogue", fetch=self.fetch))

    def test_prereleases_and_untrusted_versions_are_rejected(self):
        release = self.responses["repos/librenms/librenms/releases/latest"]
        for bad in ({"prerelease": True}, {"draft": True}, {"tag_name": "26.10.2-rc1"}, {"tag_name": "../../other"}):
            saved = dict(release)
            release.update(bad)
            with self.assertRaises(ValueError):
                upstream.release_plan("example/catalogue", fetch=self.fetch)
            release.clear()
            release.update(saved)
        with self.assertRaises(ValueError):
            upstream.release_plan("example/catalogue", "$(anything)", self.fetch)

    def test_manual_release_uses_the_official_release_endpoint(self):
        self.responses["repos/librenms/librenms/releases/tags/26.10.2"] = self.responses["repos/librenms/librenms/releases/latest"]
        self.assertEqual("26.10.2", upstream.release_plan("example/catalogue", "26.10.2", self.fetch)["version"])

    def test_lookup_failures_do_not_publish(self):
        def unavailable(endpoint):
            raise RuntimeError("GitHub unavailable")
        with self.assertRaises(RuntimeError):
            upstream.release_plan("example/catalogue", fetch=unavailable)

    def test_feed_promotion_is_monotonic_and_idempotent(self):
        self.assertTrue(promote.promotion_needed({"catalogueVersion": "1.0.1"}, {"catalogueVersion": "26.10.2"}))
        self.assertFalse(promote.promotion_needed({"catalogueVersion": "26.10.2"}, {"catalogueVersion": "26.10.2"}))
        with self.assertRaisesRegex(ValueError, "downgrade"):
            promote.promotion_needed({"catalogueVersion": "26.10.2"}, {"catalogueVersion": "26.9.0"})
        with self.assertRaisesRegex(ValueError, "conflicting"):
            promote.promotion_needed({"catalogueVersion": "26.10.2"}, {"catalogueVersion": "26.10.2", "shards": []})
        self.assertTrue(promote.promotion_needed({"catalogueVersion": "26.10.2"}, {"catalogueVersion": "26.10.2+catalogue.1"}))
        self.assertTrue(promote.promotion_needed({"catalogueVersion": "26.10.2+catalogue.1"}, {"catalogueVersion": "26.10.3"}))
        with self.assertRaisesRegex(ValueError, "downgrade"):
            promote.promotion_needed({"catalogueVersion": "26.10.2+catalogue.1"}, {"catalogueVersion": "26.10.2"})


if __name__ == "__main__":
    unittest.main()
