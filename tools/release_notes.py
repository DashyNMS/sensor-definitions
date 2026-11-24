"""The notes people read with a catalogue.

A catalogue's version is LibreNMS's to choose, so its notes are written in
docs/releases/next.md until it's published. Publishing puts them above the
generated summary, and activating it renames the file to the version and starts
the next one. A catalogue with no changes of ours has only the summary.
"""
from pathlib import Path
import re
import sys

HEADINGS = ("Breaking", "New", "Changed", "Fixed")
NEXT = "docs/releases/next.md"
BLANK = ("Notes for the next catalogue. Add a line under ## Breaking, ## New, ## Changed or ## Fixed "
         "when a change alters what people see.\n")


def pending(text):
    """The notes in next.md, checked, or nothing when there are no changes to tell people about."""
    headings = re.findall(r"^## (.+)$", text, re.M)
    unknown = [heading for heading in headings if heading not in HEADINGS]
    if unknown:
        raise ValueError(f"{NEXT} has the heading {unknown[0]!r}. Use {', '.join(HEADINGS)}.")
    if not headings:
        if re.search(r"^- ", text, re.M):
            raise ValueError(f"{NEXT} has a change that isn't under a heading.")
        return ""
    if not re.search(r"^- \S", text, re.M):
        raise ValueError(f"{NEXT} has a heading with no changes.")
    return text[text.index("## "):].strip() + "\n"


def with_notes(text, summary):
    notes = pending(text)
    return f"{notes}\n---\n\n{summary}" if notes else summary


def archive(root, version, published):
    """Give the published notes their version. Left alone if they've changed since, or say nothing."""
    path = Path(root) / NEXT
    if not path.is_file() or path.read_text(encoding="utf-8") != published or not pending(published):
        return False
    (path.parent / f"{version}.md").write_text(pending(published), encoding="utf-8", newline="\n")
    path.write_text(BLANK, encoding="utf-8", newline="\n")
    return True


if __name__ == "__main__":
    try:
        pending((Path(__file__).resolve().parents[1] / NEXT).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        sys.exit(str(error))
