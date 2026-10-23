"""Resolve an official stable release to a pinned commit; never execute upstream code."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
SHA = re.compile(r"[0-9a-f]{40}")


class NotFound(Exception):
    pass


def api(endpoint):
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True)
    if result.returncode:
        if "HTTP 404" in result.stderr:
            raise NotFound(endpoint)
        raise RuntimeError("GitHub release lookup failed: " + endpoint)
    return json.loads(result.stdout)


def release_plan(repository, requested="", fetch=api):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid catalogue repository")
    if requested and not VERSION.fullmatch(requested):
        raise ValueError("Use a stable LibreNMS version such as 26.10.2")
    upstream = "repos/librenms/librenms/"
    release = fetch(upstream + ("releases/tags/" + requested if requested else "releases/latest"))
    version = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease") or not VERSION.fullmatch(version) or (requested and version != requested):
        raise ValueError("Only official stable numeric LibreNMS releases can be published")
    ref = fetch(upstream + "git/ref/tags/" + version)["object"]
    for _ in range(8):
        if ref.get("type") == "commit" and SHA.fullmatch(ref.get("sha", "")):
            break
        if ref.get("type") != "tag" or not SHA.fullmatch(ref.get("sha", "")):
            raise ValueError("Release tag does not resolve to a commit")
        ref = fetch(upstream + "git/tags/" + ref["sha"])["object"]
    else:
        raise ValueError("Release tag nesting exceeds its limit")
    target = "repos/" + repository + "/"
    feed = fetch(target + "contents/feeds/v1/stable.json?ref=main")
    current = json.loads(base64.b64decode(feed["content"]))["catalogueVersion"]
    if not re.fullmatch(VERSION.pattern + r"(?:\+catalogue\.[1-9][0-9]*)?", current):
        raise ValueError("Invalid stable feed version")
    if tuple(map(int, version.split("."))) <= tuple(map(int, current.split("+")[0].split("."))):
        return None
    try:
        fetch(target + "releases/tags/v" + version)
    except NotFound:
        pass
    else:
        # Retry feed promotion after a publication succeeded but its push failed.
        return {"version": version, "revision": ref["sha"], "action": "promote"}
    try:
        fetch(target + "git/ref/tags/v" + version)
    except NotFound:
        return {"version": version, "revision": ref["sha"], "action": "build"}
    raise ValueError("Catalogue tag already exists without a release; review the incomplete publication before retrying")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", default="")
    parser.add_argument("--pin", action="store_true", help="Record the resolved input in the local source lock")
    args = parser.parse_args()
    plan = release_plan(os.environ["GITHUB_REPOSITORY"], args.release)
    output = {"publish": "true" if plan else "false", **(plan or {})}
    if plan and args.pin:
        path = ROOT / "sources/librenms.json"
        lock = json.loads(path.read_text())
        lock.update(revision=plan["revision"], release=plan["version"])
        path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.writelines(f"{key}={value}\n" for key, value in output.items())
    print(json.dumps(output))


if __name__ == "__main__":
    main()
