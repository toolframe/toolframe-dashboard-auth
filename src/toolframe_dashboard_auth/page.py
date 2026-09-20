"""UI-only auth integration; credentials remain in the auth service."""

from datetime import UTC, datetime, timedelta

from toolframe_sdk import PluginError


def timestamp(value):
    return (
        datetime.fromtimestamp(value, UTC).isoformat(timespec="seconds")
        if value is not None
        else "—"
    )


def grant_fields(st, catalog, prefix, record=None):
    record = record or {}
    label = st.text_input("Name", value=record.get("label", ""), key=f"{prefix}-label")
    all_business = st.checkbox(
        "All business scopes (including future plugins)",
        value=record.get("all_business", True),
        key=f"{prefix}-all",
    )
    scopes = []
    owners = sorted({item["owner"] for item in catalog.values()})
    for owner in owners:
        options = [name for name, item in catalog.items() if item["owner"] == owner]
        selected = st.multiselect(
            f"{owner} scopes",
            options,
            default=[s for s in record.get("scopes", []) if s in options],
            format_func=lambda s: f"{catalog[s]['title']} ({s})",
            key=f"{prefix}-{owner}",
        )
        scopes.extend(selected)
    expiry = record.get("expires_at")
    limited = st.checkbox(
        "Set expiry", value=expiry is not None, key=f"{prefix}-limited"
    )
    default = (
        datetime.fromtimestamp(expiry, UTC)
        if expiry
        else datetime.now(UTC) + timedelta(days=7)
    )
    date = st.date_input(
        "Expiry date (UTC)",
        value=default.date(),
        key=f"{prefix}-date",
    )
    time = st.time_input(
        "Expiry time (UTC)",
        value=default.time(),
        key=f"{prefix}-time",
    )
    expires_at = datetime.combine(date, time, UTC).timestamp() if limited else None
    return {
        "label": label,
        "scopes": scopes,
        "all_business": all_business,
        "expires_at": expires_at,
    }


def render(context):
    import streamlit as st

    st.title("Access passwords")
    try:
        settings = context.auth("catalog")
        records = context.auth("list")["credentials"]
    except PluginError as error:
        st.error(error.message)
        return
    if context.can("system.settings.manage"):
        with st.expander("Application access policy"):
            mode = st.selectbox(
                "Dashboard access",
                ["public", "protected"],
                index=0 if settings["policy"]["mode"] == "public" else 1,
            )
            local = st.checkbox(
                "Allow direct local control", value=settings["policy"]["local_control"]
            )
            if st.button("Save access policy"):
                try:
                    context.auth(
                        "policy",
                        {
                            "mode": mode,
                            "local_control": local,
                            "expected_revision": settings["revision"],
                        },
                    )
                    st.rerun()
                except PluginError as error:
                    st.error(error.message)
    st.caption(
        "System scopes are excluded by default. Names identify grants, not people. MCP, llms.txt and explicitly public business APIs stay public."
    )
    with st.form("create-password", clear_on_submit=False):
        st.subheader("New access password")
        fields = grant_fields(st, settings["scopes"], "new")
        generate = st.checkbox("Generate a random password", value=True)
        custom = st.text_input(
            "Custom password (12–1024 characters; ignored when generating)",
            type="password",
            max_chars=1024,
        )
        create = st.form_submit_button("Create password")
    if create:
        try:
            result = context.auth(
                "create",
                {
                    **fields,
                    "password": None if generate else custom,
                    "expected_revision": settings["revision"],
                },
            )
        except PluginError as error:
            st.error(error.message)
        else:
            st.success(
                "Password created. Copy the generated password now; it cannot be retrieved later."
            )
            if result.get("password"):
                st.code(result["password"], language=None)
            if result.get("policy_error"):
                st.error(result["policy_error"])
            records = context.auth("list")["credentials"]
    st.subheader("Password records")
    st.dataframe(
        [
            {
                **{k: v for k, v in row.items() if k not in {"scopes", "all_business"}},
                "scopes": ", ".join(row["scopes"]),
                "all_business": row["all_business"],
                **{
                    k: timestamp(row[k])
                    for k in (
                        "created_at",
                        "expires_at",
                        "revoked_at",
                        "last_login",
                        "last_used",
                    )
                },
            }
            for row in records
        ],
        hide_index=True,
        width="stretch",
    )
    if st.button("Refresh records"):
        st.rerun()
    if records:
        identifier = st.selectbox(
            "Password record",
            [r["id"] for r in records],
            format_func=lambda key: next(r["label"] for r in records if r["id"] == key),
        )
        record = next(r for r in records if r["id"] == identifier)
        if record["revoked_at"] is not None:
            st.info("Revoked. Create a new record to issue a new authorization.")
            return
        with st.form(f"edit-{identifier}"):
            fields = grant_fields(st, settings["scopes"], identifier, record)
            edit = st.form_submit_button("Save password grant")
        if edit:
            try:
                context.auth("update", {"id": identifier, **fields})
                st.rerun()
            except PluginError as error:
                st.error(error.message)
        if st.button("Revoke password", type="primary"):
            try:
                context.auth("revoke", {"id": identifier})
                st.rerun()
            except PluginError as error:
                st.error(error.message)
