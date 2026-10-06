#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_repository="${TOOLFRAME_SDK_REPOSITORY:-$project_root/../toolframe-sdk}"
sdk_revision=871416a9f9cbcfa79298235781ff193e1ad08a12
python_version=3.14.7

# Neither checkout's .venv, dist, lockfile nor working tree is modified.
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/dashboard-auth-ci.XXXXXX")"
printf 'Validation workspace: %s\n' "$work_dir"
trap 'printf "Validation workspace retained at: %s\n" "$work_dir"' EXIT
source_dir="$work_dir/toolframe-dashboard-auth"
mkdir -p "$source_dir" "$work_dir/toolframe-sdk" "$work_dir/wheelhouse" \
  "$work_dir/dist" "$work_dir/empty-cwd"
tar --exclude='.git' --exclude='.venv' --exclude='dist' \
  --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
  -cf - -C "$project_root" . | tar -xf - -C "$source_dir"
git -C "$sdk_repository" archive "$sdk_revision" | tar -xf - -C "$work_dir/toolframe-sdk"
printf 'SDK revision: %s\n' "$sdk_revision"

unset PYTHONPATH PYTHONHOME VIRTUAL_ENV
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 UV_NO_PROGRESS=1
export UV_CACHE_DIR="$work_dir/uv-cache"
python_path="$(uv python find --system "$python_version")"
"$python_path" --version
uv --version
cd "$source_dir"

# Check the existing lock against the pinned SDK, then retain its dependency versions.
# Local projects are supplied as the freshly built wheels below.
uv export --locked --no-hashes --no-emit-project --no-emit-package toolframe-sdk \
  --output-file "$work_dir/test-requirements.txt" > /dev/null
uv build --no-sources --python "$python_path" --wheel \
  --out-dir "$work_dir/wheelhouse" "$work_dir/toolframe-sdk"
# With no format flags, uv builds an sdist and then a wheel from that sdist.
uv build --no-sources --python "$python_path" --out-dir "$work_dir/dist"

sdk_wheels=("$work_dir"/wheelhouse/*.whl)
project_wheels=("$work_dir"/dist/*.whl)
test_python="$work_dir/test-venv/bin/python"
uv venv --python "$python_path" "$work_dir/test-venv"
# Compile pure-Python dependency bytecode during setup to reduce first-import work.
uv pip install --python "$test_python" --no-sources --strict --compile-bytecode \
  -r "$work_dir/test-requirements.txt" \
  "${sdk_wheels[0]}" "${project_wheels[0]}[ui]" 'twine==7.0.0'
uv pip check --python "$test_python"
"$test_python" -m ruff check src tests scripts
(
  cd "$work_dir/empty-cwd"
  "$test_python" -I -m pytest -q -p no:cacheprovider --durations=5 "$source_dir/tests"
)
"$test_python" -m twine check --strict "$work_dir"/dist/*.whl "$work_dir"/dist/*.tar.gz

# A separate environment receives only the actual runtime dependencies, no dev tools.
runtime_python="$work_dir/runtime-venv/bin/python"
uv venv --python "$python_path" "$work_dir/runtime-venv"
uv pip install --python "$runtime_python" --no-sources --strict \
  "${sdk_wheels[0]}" "${project_wheels[0]}"
uv pip check --python "$runtime_python"
cd "$work_dir/empty-cwd"
"$runtime_python" -I "$source_dir/scripts/wheel_smoke.py"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  printf 'dist-dir=%s\n' "$work_dir/dist" >> "$GITHUB_OUTPUT"
fi
printf 'All validation passed. Distributions: %s/dist\n' "$work_dir"
