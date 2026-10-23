"""Run repeatable security checks without printing candidate secrets."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "artifacts/security"
    output.mkdir(parents=True, exist_ok=True)
    checks = [
        [sys.executable, "-m", "pip_audit", "--strict", "-r", "requirements.txt", "-r", "requirements-security.txt", "-f", "json", "-o", str(output / "dependencies.json")],
        [sys.executable, "-m", "bandit", "-r", "tools", "-ll", "-f", "json", "-o", str(output / "bandit.json")],
    ]
    failed = False
    for command in checks:
        result = subprocess.run(command, cwd=ROOT, check=False)
        failed = failed or result.returncode != 0
    result = subprocess.run([sys.executable, "-m", "detect_secrets", "scan", "--no-verify", "--filter", "tools/security_filters.py::is_catalogue_digest"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        print("Secret scan failed; inspect the scanner configuration.")
        failed = True
    else:
        report = json.loads(result.stdout)
        (output / "secrets.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        count = sum(len(items) for items in report["results"].values())
        print(f"Secret scan: {count} potential findings. Report: artifacts/security/secrets.json")
        failed = failed or count > 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
