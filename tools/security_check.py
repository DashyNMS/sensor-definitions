"""Run the common security gate; retained for the documented catalogue command."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/security_check.py"), run_name="__main__")
