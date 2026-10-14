# Toolframe Dashboard Auth

The `dashboard-auth` provider supplies password and configured OIDC login choices,
plus Streamlit access-management pages. It depends on the `toolframe.auth` service
and SDK 0.2–0.3. Core handles cookies, admission and protected auth API calls; this
plugin holds no credential database or verifier key.

Install the package in a running application with compatible Auth and Dashboard
providers, then open **Access passwords** as a local operator:

```sh
toolframe --home APP plugin add pypi:toolframe-dashboard-auth==0.1.3 --enable
```

With Core 0.6.1, **Access by entrance** reports Dashboard/service access, independent
MCP policy, declared public HTTP methods and the current local/operator context.
The policy form lets settings administrators choose closed or public behavior
when Dashboard authentication fails. Closed is the default for new applications;
existing application choices are preserved. Older Core versions keep the existing
policy controls but do not offer the unsupported failure-policy editor. Public
HTTP declarations and llms documents remain public, and method scopes do not
provide per-person row isolation.
While this page is available, credential-list errors leave its policy controls
usable by local operators. If Dashboard Auth itself is unavailable, use Core's
local management API for recovery.

With compatible Core/Auth and `toolframe-oidc-auth` installed, the login page
loads provider buttons from Core's safe provider catalogue. **Connected agents**
requires `system.auth.self` and lets a federated user revoke their own connections
without logging out. **User access** requires `system.auth.users` and manages
permissions/disablement for identities already admitted by application
configuration. Disabling a user revokes their browser sessions and agent grants.
The pages call Core's protected facade; no upstream credentials enter Streamlit.

The optional **MCP keys** page requires `system.auth.mcp_keys` and manages named
256-bit bearer keys through core's separate MCP auth API. Install/enable
`toolframe-mcp-auth` to generate keys, select business scopes and expiry, copy each
secret once and revoke it later. `system.settings.manage` also permits changing
the independent MCP public/protected policy. The page remains available for policy
recovery when the MCP auth provider is absent. See the MCP authentication guide
in the core repository for configuration details.

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

For release validation and Trusted Publisher setup, see [releasing](docs/releasing.md).

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
