# CI and publishing

## Run the CI checks locally

Use Git, Bash, Python **3.14.7** and uv **0.12.8**, with network access to PyPI.
The SDK checkout must contain commit
`ef91b609137a5fe7bae8e0c893e74b096ff06ffe` (SDK 0.3.0).

```sh
uv python install 3.14.7
bash scripts/ci.sh
```

By default the script reads `../toolframe-sdk`. To use a different checkout:

```sh
TOOLFRAME_SDK_REPOSITORY=/absolute/path/to/toolframe-sdk bash scripts/ci.sh
```

Each invocation creates and prints a new temporary workspace. It copies this
working tree and archives the exact SDK commit there; it does not build from
the SDK's current working tree. It leaves both original repositories, their
lockfiles, existing `.venv` directories and existing `dist` directories alone.
The temporary workspace is retained on success or failure for inspection.

The script performs these checks, stopping on any failure:

1. Export the existing `uv.lock` with `uv export --locked`, retaining the locked
   development dependency versions, including Streamlit 1.61.0. Exclude the two
   editable project entries because fresh wheels supply them instead.
2. Build the SDK wheel and this project's sdist and wheel with `uv build
   --no-sources`. The project wheel is built from its sdist by uv's default build
   sequence. All build directories and the uv cache start empty.
3. Install the new SDK and plugin wheels with the `ui` extra, locked development
   dependencies and Twine 7.0.0 into a new test environment, compiling dependency
   bytecode before the existing Streamlit AppTest deadlines start. Run `uv pip check`,
   `ruff check src tests scripts`, all existing presentation tests via
   `python -I -m pytest -q -p no:cacheprovider --durations=5 <copied-source>/tests`
   from an empty working directory, and
   `twine check --strict` on both distributions.
4. Install both wheels into another empty environment with their real runtime
   dependencies. Run `uv pip check` and the wheel smoke check from outside the
   source tree using Python's isolated mode. Check installed module paths,
   versions, plugin discovery, scoped management-page metadata, bundled password
   login HTML, and the unchanged Apache-2.0 `LICENSE` and `NOTICE` files.

The runtime smoke environment contains no Streamlit or development tools; the
presentation tests exercise Streamlit in the test environment. Neither install
uses `--no-deps`. Only this project's two distributions are upload artifacts;
the SDK wheel is a local validation dependency and is never uploaded by this repo.
Twine is pinned to 7.0.0 for its
[Metadata 2.5 compatibility fix](https://twine.readthedocs.io/en/stable/changelog.html#twine-7-0-0-2026-07-27).

Workflow and shell syntax checks can also be run from the repository root:

```sh
actionlint .github/workflows/*.yml
bash -n scripts/ci.sh
python3.14 scripts/check_release_tag.py refs/tags/v0.1.3
```

## GitHub Actions

`ci.yml` handles pull requests, pushes to `main`, and manual runs. It calls
`validate.yml`, which runs the same local script on `ubuntu-24.04` and `macos-15`,
with Python 3.14.7 and uv 0.12.8. These labels appear in the
[official runner list](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
Successful Linux validation retains the wheel and sdist for seven days as
`dashboard-auth-dist-<commit SHA>`. Both matrix jobs must pass for validation to
succeed. Jobs have bounded timeouts and default to `contents: read`.

All external actions use full commit pins with version comments. Checkouts do not
persist credentials. CI concurrency cancels superseded runs; the reusable
workflow has no concurrency group and cannot cancel its caller. There is no
`pull_request_target` execution or automatic publishing from PRs or tag pushes.

Before remote runs, push this repository and the pinned SDK commit to the chosen
GitHub owner. The dependency repository must be named `toolframe-sdk`; its owner
defaults to `github.repository_owner`. Set the repository Actions variable
`TOOLFRAME_REPOSITORY_OWNER` if the SDK lives under another trusted owner. Fork
PRs still fetch from this configured/base owner, never the PR author's owner.
Public siblings need no additional token. For private SDK access, configure the
read-only `TOOLFRAME_READ_TOKEN` described in [releasing](releasing.md). The
current repository's `GITHUB_TOKEN` cannot read a different private repository.

## Publication

See [releasing](releasing.md) for dependency order, private repository access,
Trusted Publisher bindings, version tags and consumer installation checks.

## Validation limits

Local validation runs on the host executing the script. Passing it on an Apple
Silicon Mac does not claim an executed GitHub Linux/macOS matrix, Windows or
physical Intel support, full Core/auth integration, browser automation, or an
actual OIDC upload. Presentation behavior is covered by the existing Streamlit
AppTest suite; authentication enforcement remains owned by Core/auth. Preparing
these files does not push commits, create tags remotely, register publishers or
deploy a release.

The first Streamlit AppTest render has a bounded 60-second timeout to allow
cold native-library imports. Later interactions retain their shorter timeout;
assertions remain active and the suite does not retry failures.
