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
BLANK = ("Notes for the next catalogue. When a change alters what people see, add a line for it under a "
         "Breaking, New, Changed or Fixed heading.\n")


def sections(text):
    """The headings and their changes, or nothing when there are no changes to tell people about."""
    found = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            if current not in HEADINGS:
                raise ValueError(f"{NEXT} has the heading {current!r}. Use {', '.join(HEADINGS)}.")
            found.setdefault(current, [])
        elif current is not None and line.strip():
            found[current].append(line)
        elif line.startswith("- "):
            raise ValueError(f"{NEXT} has a change that isn't under a heading.")
    for heading, lines in found.items():
        if not any(line.startswith("- ") for line in lines):
            raise ValueError(f"{NEXT} has no changes under {heading}.")
    return found


def render(found):
    return "\n".join(f"## {heading}\n\n" + "\n".join(found[heading]) + "\n" for heading in HEADINGS if found.get(heading))


def pending(text):
    return render(sections(text))


def with_notes(text, summary):
    notes = pending(text)
    return f"{notes}\n---\n\n{summary}" if notes else summary


def archive(root, version, published):
    """Give the published notes their version, and keep in next.md only what has been added since."""
    notes = sections(published)
    path = Path(root) / NEXT
    if not notes or not path.is_file():
        return False
    kept = {heading: [line for line in lines if line not in notes.get(heading, [])]
            for heading, lines in sections(path.read_text(encoding="utf-8")).items()}
    later = render(kept)
    (path.parent / f"{version}.md").write_text(render(notes), encoding="utf-8", newline="\n")
    path.write_text(BLANK + (f"\n{later}" if later else ""), encoding="utf-8", newline="\n")
    return True


if __name__ == "__main__":
    try:
        pending((Path(__file__).resolve().parents[1] / NEXT).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        sys.exit(str(error))
