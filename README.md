# Toolframe Dashboard Auth

The `dashboard-auth` provider supplies a password-only login page and an ordinary
Streamlit **Access passwords** page. It depends on the `toolframe.auth` service
and SDK 0.2. Core handles cookies, admission and protected auth API calls; this
plugin holds no credential database or verifier key.

The management page fills in an editable **Unnamed password** label, adding a
number for names already in use. The password field accepts 8–32 characters and
shows a stable random suggestion as its placeholder. Leave the field blank to use
that exact suggestion; after creation, copy the one-time displayed password.
Failed submissions preserve the draft; successful creation starts a fresh one.

**Set expiry** immediately reveals a duration and unit side by side, with minutes,
hours, days, weeks or calendar months and a calculated local expiry preview.
Preview and record timestamps use the browser's timezone (its UTC offset is a
fallback, then UTC if neither is available). Durations start when saved; months
follow that local calendar and clamp to the destination month's last day. Other
units measure elapsed time, including across daylight-saving changes. No
date/time entry is needed.
Turning expiry off hides the controls and saves no expiry. When editing, leave the
duration blank to preserve the exact existing expiry, or enter a duration to
replace it. Saving other grant fields never silently extends the expiry.

The page selects scopes, edits grants, revokes records and shows creation,
last-login and last-use timestamps. Its page
requires `system.auth.passwords`; access-policy controls additionally require
`system.settings.manage`. Core/auth enforce the same rules beyond the UI.

Core serves the login page at `/_toolframe/auth/login`. The existing Dashboard
provider owns the common local/public/protected header so it remains available
when this integration fails or is disabled. Streamlit is supplied by the shared
Dashboard execution environment, not the business/auth worker.

```sh
uv sync
uv run pytest -q
uv run ruff check src tests
uv build --wheel
```

For the same isolated validation used by GitHub Actions, run `bash scripts/ci.sh`
with Python 3.14.7, uv 0.12.8 and a sibling `toolframe-sdk` Git checkout available.
This runs the presentation tests against a newly built wheel, checks both
distributions, and verifies a separate installation with only runtime dependencies.
See [CI and publishing](docs/ci.md) for the pinned SDK revision, workflow triggers,
release prerequisites and local validation limits.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
