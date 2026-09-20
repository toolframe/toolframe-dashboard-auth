# Toolframe Dashboard Auth

The `dashboard-auth` provider supplies a password-only login page and an ordinary
Streamlit **Access passwords** page. It depends on the `toolframe.auth` service
and SDK 0.2. Core handles cookies, admission and protected auth API calls; this
plugin holds no credential database or verifier key.

The management page creates generated/custom passwords, selects scopes and an
optional UTC expiry, edits expiry/grants, revokes records and shows creation,
last-login and last-use timestamps. Generated secrets are revealed once. Its page
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
