"""Require the workflow ref to be the exact tag declared by project.version."""

import os
import sys
import tomllib
from pathlib import Path

project = Path(__file__).resolve().parents[1] / "pyproject.toml"
version = tomllib.loads(project.read_text())["project"]["version"]
expected = f"refs/tags/v{version}"
ref = sys.argv[1] if len(sys.argv) == 2 else os.environ.get("GITHUB_REF", "")
if ref != expected:
    raise SystemExit(f"Publishing requires {expected}; received {ref!r}")
print(f"Validated release tag: {ref}")
