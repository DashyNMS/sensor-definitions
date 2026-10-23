"""Activate validated immutable release data without changing any repository permissions."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def promotion_needed(current, incoming):
    versions = [item.get("catalogueVersion", "") for item in (current, incoming)]
    if any(not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version) for version in versions):
        raise ValueError("Invalid feed version")
    old, new = (tuple(map(int, version.split("."))) for version in versions)
    if new < old:
        raise ValueError("Refusing to downgrade the stable feed")
    if new == old and current != incoming:
        raise ValueError("An immutable catalogue version has conflicting manifests")
    return new > old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", args.version) or not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise ValueError("Invalid release identity")
    tag = "v" + args.version
    run("gh", "release", "view", tag, "--json", "tagName")
    run("git", "fetch", "origin", "main", "refs/tags/" + tag + ":refs/tags/" + tag)
    lock = json.loads(run("git", "show", tag + ":sources/librenms.json"))
    if lock.get("release") != args.version or lock["revision"] != args.revision:
        raise ValueError("Published catalogue does not match the official LibreNMS release")
    manifest = run("git", "show", tag + ":data/manifest.json") + "\n"
    incoming = json.loads(manifest)
    if incoming["catalogueVersion"] != args.version:
        raise ValueError("Published catalogue version mismatch")
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory) / "promotion"
        run("git", "worktree", "add", "--detach", str(work), "origin/main")
        try:
            feed = work / "feeds/v1/stable.json"
            if not promotion_needed(json.loads(feed.read_text()), incoming):
                print("Stable feed already uses " + args.version)
                return
            feed.write_text(manifest, encoding="utf-8")
            run("git", "add", "feeds/v1/stable.json", cwd=work)
            run("git", "commit", "-m", "build(updates): activate LibreNMS " + args.version + " definitions", cwd=work)
            # No force push: a concurrent main change causes a retryable failure.
            run("git", "push", "origin", "HEAD:refs/heads/main", cwd=work)
            print("Stable feed activated: " + args.version)
        finally:
            run("git", "worktree", "remove", str(work))


if __name__ == "__main__":
    main()
