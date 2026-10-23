"""Publish immutable tagged data and leave its manifest ready for a reviewed feed PR."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", args.version):
        raise ValueError("Use a stable numeric version")
    manifest = json.loads((args.data / "manifest.json").read_text())
    if manifest["catalogueVersion"] != args.version:
        raise ValueError("Manifest version mismatch")
    lock_path = Path("sources/librenms.json")
    lock = json.loads(lock_path.read_text())
    coverage = json.loads((args.data / "coverage.json").read_text())
    if coverage["upstreamRevision"] != lock["revision"]:
        raise ValueError("Generated data does not match the pinned source revision")
    repository = os.environ["GITHUB_REPOSITORY"]
    tag = "v" + args.version
    if subprocess.run(["git", "rev-parse", "--verify", "refs/tags/" + tag], capture_output=True).returncode == 0:
        raise ValueError("An immutable release tag already exists")
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    # The tag includes source and generated data. Shards are fetched from raw
    # GitHub at this immutable tag, avoiding hundreds of release attachments.
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder) / "publication"
        run("git", "worktree", "add", "--detach", str(work), "HEAD")
        shutil.copytree(args.data, work / "data")
        # Scheduled builds resolve a release rather than main's research pin.
        # The immutable tag must retain that exact source lock for reproduction.
        shutil.copyfile(lock_path, work / "sources/librenms.json")
        run("git", "add", "data", "sources/librenms.json", cwd=work)
        run("git", "commit", "-m", f"build(definitions): publish catalogue {args.version}", cwd=work)
        run("git", "tag", tag, cwd=work)
        run("git", "push", "origin", "refs/tags/" + tag, cwd=work)
        notes = Path(folder) / "notes.md"
        notes.write_text(f"Sensor state catalogue {args.version}: {coverage['definitions']} definitions for {coverage['systems']} systems.\n\n"
                         f"LibreNMS source: `{coverage['upstreamRevision']}`.\n\n"
                         "Data is split by device OS and downloaded on demand. Source notices are included in the tagged data and notices asset. "
                         "Unsupported and dynamic discovery cases are recorded in the CI coverage report.\n", encoding="utf-8")
        run("gh", "release", "create", tag, "--repo", repository, "--title", f"Sensor definitions {args.version}",
            "--notes-file", str(notes), str(args.data / "manifest.json"), str(args.data / "notices.txt"))
        run("git", "worktree", "remove", str(work))
        print(f"Published {tag}. Submit artifacts/release/manifest.json as feeds/v1/stable.json in a reviewed PR.")


if __name__ == "__main__":
    main()
