"""Work out an edge or nightly build's version, tag and notes.

    edge      <LibreNMS release>-edge.<run number>       every commit to main
    nightly   <LibreNMS release>-nightly.<run number>    00:00 UTC if main changed, or by hand

The release is the pinned one in sources/librenms.json. The result goes to
$GITHUB_OUTPUT: version, tag, commit and changed. Other DashyNMS repositories'
scripts/build_version.py does the same from Directory.Build.props.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_notes  # noqa: E402


def git(*args):
    return subprocess.run(("git", *args), check=True, capture_output=True, text=True).stdout.strip()


def newest(*patterns):
    for pattern in patterns:
        tags = git("tag", "--list", pattern, "--merged", "HEAD", "--sort=-creatordate").splitlines()
        if tags:
            return tags[0]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("channel", choices=["edge", "nightly"])
    parser.add_argument("--notes", type=Path, required=True)
    args = parser.parse_args()

    release = json.loads(Path("sources/librenms.json").read_text(encoding="utf-8"))["release"]
    number = os.environ.get("GITHUB_RUN_NUMBER", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", release) or not re.fullmatch(r"[1-9]\d*", number):
        raise SystemExit("The pinned LibreNMS release and GITHUB_RUN_NUMBER must be numeric.")
    version = f"{release}-{args.channel}.{number}"
    commit = git("rev-parse", "HEAD")
    # Catalogue tags are on commits of their own, so only these channels' tags are in main's history.
    last = newest("v*-nightly.*") if args.channel == "nightly" else newest("v*-edge.*", "v*-nightly.*")
    changed = (args.channel == "edge" or os.environ.get("GITHUB_EVENT_NAME") != "schedule"
               or not git("tag", "--list", "v*-nightly.*", "--points-at", "HEAD"))

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    link = f" [Changes since {last}](https://github.com/{repository}/compare/{last}...v{version})." if last else ""
    summary = (f"A build of {commit[:7]} from LibreNMS {release}, for testing a change. It isn't in the live feed, "
               f"so no app uses it.{link}\n")
    text = Path(release_notes.NEXT).read_text(encoding="utf-8")
    args.notes.parent.mkdir(parents=True, exist_ok=True)
    args.notes.write_text(summary if args.channel == "edge" else release_notes.with_notes(text, summary), encoding="utf-8", newline="\n")

    result = {"version": version, "tag": f"v{version}", "commit": commit, "changed": str(changed).lower()}
    lines = "".join(f"{key}={value}\n" for key, value in result.items())
    sys.stdout.write(lines)
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(lines)


if __name__ == "__main__":
    main()
