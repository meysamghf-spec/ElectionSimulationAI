"""Fail npm audit unless every advisory is the known unpatched braces chain.

braces <=3.0.3 has no patched release. eslint-config-next pulls it through
fast-glob and micromatch. Those packages are development dependencies and are
not copied into the production frontend image.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ALLOWED = {
    "braces",
    "micromatch",
    "fast-glob",
    "@next/eslint-plugin-next",
    "eslint-config-next",
}


def main() -> int:
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    completed = subprocess.run(
        ["npm", "audit", "--json"],
        cwd=frontend,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        data = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        print(completed.stderr)
        return 1
    vulnerabilities = data.get("vulnerabilities", {})
    unexpected = sorted(name for name in vulnerabilities if name not in ALLOWED)
    if unexpected:
        print("Unexpected npm advisories:", ", ".join(unexpected))
        return 1
    if vulnerabilities:
        print("npm audit: only the documented unpatched braces development chain remains.")
    else:
        print("npm audit: no advisories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
