"""Allow only declared public integrity hashes in their own metadata files."""
from functools import lru_cache
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=2)
def metadata_hashes(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if path == ROOT / "sources/librenms.json":
        return {value for value in [data["revision"]] if re.fullmatch(r"[0-9a-f]{40}", value)}
    return {value for value in [data["notices"]["sha256"], *(item["sha256"] for item in data["shards"])]
            if re.fullmatch(r"[0-9a-f]{64}", value)}


def is_catalogue_digest(secret, filename):
    path = (ROOT / filename).resolve()
    if path not in (ROOT / "sources/librenms.json", ROOT / "feeds/v1/stable.json"):
        return False
    return secret in metadata_hashes(path)
