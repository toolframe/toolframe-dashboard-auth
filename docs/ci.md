# CI and publishing

## Run the CI checks locally

Use Git, Bash, Python **3.14.7** and uv **0.12.8**, with network access to PyPI.
The SDK checkout must contain commit
`121e60eb5ba77717a382cd474c7a31d2de086d13` (SDK 0.2.0).

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
python3.14 scripts/check_release_tag.py refs/tags/v0.1.1
```

## GitHub Actions

`ci.yml` handles pull requests, pushes (including tags), and manual runs. It calls
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
The SDK repository must be publicly readable for this credential-free
cross-repository checkout. A private SDK requires a separately designed read-only
credential arrangement; the current repository's `GITHUB_TOKEN` cannot read a
different private repository by default.

## Prepare TestPyPI and PyPI publishing

`publish.yml` is manual only. Its `environment` choice defaults to `testpypi` and
also offers `pypi`. The selected Git ref must be exactly
`refs/tags/v<project.version>`; the current version requires `v0.1.1`. A branch,
missing `v`, or different version fails before validation and upload.

Configure these external prerequisites before running it:

1. Make `publish.yml` available on the repository's default branch so GitHub can
   offer manual dispatch. Ensure the matching version tag contains these workflow
   files and the intended release source.
2. Create GitHub environments named `testpypi` and `pypi`. Configure their allowed
   deployment tags and any required reviewers to suit release policy.
3. On **each** index, configure an existing or pending GitHub Trusted Publisher
   for package `toolframe-dashboard-auth`: use the actual GitHub owner, this
   repository's actual name, workflow filename **`publish.yml`**, and the matching
   environment **`testpypi`** or **`pypi`**. No PyPI API-token secret is used.
4. Make SDK 0.2.0 available to downstream installers before claiming the released
   package is installable using an index alone. The local dependency wheel proves
   installation with real dependencies, not public index availability.

After those settings are ready, manually run **Publish package** on the matching
tag, first selecting TestPyPI. The tag guard reads `pyproject.toml` from that same
revision, and both validation jobs rebuild and test that revision. The publishing
job downloads only this run's validated Linux distributions; it does not check out
or rebuild source. It uses the selected GitHub environment and the PyPA publish
action. Only that publishing job receives `id-token: write`, following
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
TestPyPI uses `https://test.pypi.org/legacy/`; PyPI uses the action's default index.
The workflow does not silently skip files that already exist on an index.

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
