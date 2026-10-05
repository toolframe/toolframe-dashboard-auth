"""UI-only auth integration; credentials remain in the auth service."""

import calendar
import secrets
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from toolframe_sdk import PluginError


def browser_timezone(name, offset):
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError, ValueError:
            pass
    if offset is not None and -1440 < offset < 1440:
        return timezone(-timedelta(minutes=offset))
    return UTC


def timestamp(value, zone=UTC):
    return (
        datetime.fromtimestamp(value, zone).strftime("%Y-%m-%d %H:%M:%S %Z")
        if value is not None
        else "—"
    )


def unnamed_label(records):
    labels = {record["label"] for record in records}
    label, number = "Unnamed password", 1
    while label in labels:
        number += 1
        label = f"Unnamed password {number}"
    return label


def expiry_after(now, amount, unit):
    if unit == "Months":
        month = now.year * 12 + now.month - 1 + amount
        year, month = divmod(month, 12)
        month += 1
        return now.replace(
            year=year,
            month=month,
            day=min(now.day, calendar.monthrange(year, month)[1]),
        ).timestamp()
    seconds = {"Minutes": 60, "Hours": 3600, "Days": 86400, "Weeks": 604800}[unit]
    return now.timestamp() + amount * seconds


def expiry_fields(st, prefix, expiry=None, zone=UTC):
    limited = st.checkbox(
        "Set expiry", value=expiry is not None, key=f"{prefix}-limited"
    )
    if not limited:
        return None
    with st.container(key=f"expiry-controls-{prefix}"):
        duration_column, unit_column = st.columns(2, gap="small")
    amount = duration_column.number_input(
        "Expire after",
        min_value=1,
        max_value=3650,
        value=None if expiry is not None else 1,
        step=1,
        placeholder="Keep current expiry",
        help="From the time you save. Leave blank to keep an existing expiry.",
        key=f"{prefix}-duration",
    )
    unit = unit_column.selectbox(
        "Unit",
        ["Minutes", "Hours", "Days", "Weeks", "Months"],
        index=3,
        key=f"{prefix}-unit",
    )
    result = expiry_after(datetime.now(zone), amount, unit) if amount else expiry
    if result is not None:
        st.caption(f"Expires on {timestamp(result, zone)}")
    else:
        st.caption("Enter a duration to set an expiry.")
    return result


def grant_fields(st, catalog, prefix, record=None, default_label="", zone=UTC):
    record = record or {}
    label = st.text_input(
        "Name",
        value=record.get("label", default_label),
        max_chars=120,
        key=f"{prefix}-label",
    )
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
    return {
        "label": label.strip() or default_label,
        "scopes": scopes,
        "all_business": all_business,
        "expires_at": expiry_fields(st, prefix, record.get("expires_at"), zone),
    }


def render(context):
    import streamlit as st

    zone = browser_timezone(st.context.timezone, st.context.timezone_offset)
    # Streamlit stacks columns below 640px; this short pair still fits side by side.
    st.html("""<style>
    [class*="st-key-expiry-controls-"] [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap;
    }
    [class*="st-key-expiry-controls-"] [data-testid="stColumn"] {
        min-width: 0; flex: 1 1 0; width: 0;
    }
    </style>""")
    st.title("Access passwords")
    try:
        settings = context.auth("catalog")
        records = context.auth("list")["credentials"]
    except PluginError as error:
        st.error(error.message)
        return
    entrances = settings.get("entrances")
    if entrances:
        with st.expander("Access by entrance", expanded=True):
            dashboard, mcp = entrances["dashboard"], entrances["mcp"]
            st.markdown(
                f"**Dashboard and service calls:** {dashboard['mode']} "
                f"(configured: {dashboard['configured']}). "
                f"**MCP:** {mcp['mode']} (configured: {mcp['configured']})."
            )
            st.caption(
                "MCP uses its own policy and credentials. Manage it on the MCP keys page. "
                "Dashboard passwords do not protect explicitly public HTTP methods or llms.txt."
            )
            st.caption(
                f"Direct local control: {'enabled' if settings['policy']['local_control'] else 'disabled'}. "
                f"Current caller: {entrances['actor']}. System operations still require operator authority or system scopes."
            )
            public = entrances["declared_public_api"]
            st.markdown("**Declared public HTTP methods**")
            for path in public:
                st.caption(path)
            if not public:
                st.caption("No public HTTP methods declared by installed plugins.")
            st.caption(
                "Declared methods are served only while their plugin is available."
            )
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
            failure = None
            if "failure_modes" in settings.get("policy_options", {}):
                failure = st.selectbox(
                    "When Dashboard authentication is unavailable",
                    ["closed", "public"],
                    index=0 if settings["policy"]["failure_mode"] == "closed" else 1,
                    format_func=lambda value: {
                        "closed": "Deny protected business access (recommended)",
                        "public": "Allow anonymous business access",
                    }[value],
                )
                if failure == "public":
                    st.warning(
                        "If authentication fails or is disabled, anonymous visitors receive all business scopes."
                    )
                st.caption(
                    "This applies to protected Dashboard/service access. MCP and public HTTP keep their own rules."
                )
            else:
                st.caption(
                    "This Core version cannot edit the authentication failure policy here."
                )
            if st.button("Save access policy"):
                try:
                    context.auth(
                        "policy",
                        {
                            "mode": mode,
                            "local_control": local,
                            "expected_revision": settings["revision"],
                            **(
                                {"failure_mode": failure} if failure is not None else {}
                            ),
                        },
                    )
                    st.rerun()
                except PluginError as error:
                    st.error(error.message)
    st.caption(
        "System scopes are excluded by default. Names identify grants, not people. MCP has a separate access policy. llms.txt and explicitly public business APIs stay public."
    )
    if "password-draft" not in st.session_state:
        st.session_state["password-draft"] = {
            "key": f"new-{secrets.token_hex(8)}",
            "label": unnamed_label(records),
            "password": secrets.token_urlsafe(24),
        }
    draft = st.session_state["password-draft"]
    # Regular widgets rerun immediately, so the expiry toggle can reveal its fields.
    with st.container(border=True):
        st.subheader("New access password")
        fields = grant_fields(
            st,
            settings["scopes"],
            draft["key"],
            default_label=draft["label"],
            zone=zone,
        )
        custom = st.text_input(
            "Password (8–32 characters)",
            type="password",
            max_chars=32,
            placeholder=draft["password"],
            help="Leave blank to use the suggested password. Copy it after creation.",
            key=f"{draft['key']}-password",
        )
        create = st.button("Create password")
    if create:
        password = custom or draft["password"]
        try:
            if not 8 <= len(password) <= 32:
                raise PluginError(
                    "invalid_request", "Passwords must contain 8–32 characters"
                )
            if (
                st.session_state[f"{draft['key']}-limited"]
                and fields["expires_at"] is None
            ):
                raise PluginError("invalid_request", "Enter an expiry duration")
            result = context.auth(
                "create",
                {
                    **fields,
                    "password": password,
                    "expected_revision": settings["revision"],
                },
            )
        except PluginError as error:
            st.error(error.message)
        else:
            st.session_state["created-password"] = {
                "password": password,
                "policy_error": result.get("policy_error"),
            }
            del st.session_state["password-draft"]
            st.rerun()
    created = st.session_state.pop("created-password", None)
    if created:
        st.success("Password created. Copy it now; it cannot be retrieved later.")
        st.code(created["password"], language=None)
        if created["policy_error"]:
            st.error(created["policy_error"])
    st.subheader("Password records")
    st.dataframe(
        [
            {
                **{k: v for k, v in row.items() if k not in {"scopes", "all_business"}},
                "scopes": ", ".join(row["scopes"]),
                "all_business": row["all_business"],
                **{
                    k: timestamp(row[k], zone)
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
        edit_key = f"{identifier}-{st.session_state.get('grant-edit-generation', 0)}"
        with st.container(border=True):
            fields = grant_fields(st, settings["scopes"], edit_key, record, zone=zone)
            edit = st.button("Save password grant")
        if edit:
            try:
                if (
                    st.session_state[f"{edit_key}-limited"]
                    and fields["expires_at"] is None
                ):
                    raise PluginError("invalid_request", "Enter an expiry duration")
                context.auth("update", {"id": identifier, **fields})
                st.session_state["grant-edit-generation"] = (
                    st.session_state.get("grant-edit-generation", 0) + 1
                )
                st.rerun()
            except PluginError as error:
                st.error(error.message)
        if st.button("Revoke password", type="primary"):
            try:
                context.auth("revoke", {"id": identifier})
                st.rerun()
            except PluginError as error:
                st.error(error.message)
