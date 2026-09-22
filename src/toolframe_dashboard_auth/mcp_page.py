"""MCP key presentation; key material is generated only by the credential service."""

import time
from urllib.parse import urlsplit, urlunsplit

from toolframe_sdk import PluginError

from .page import browser_timezone, expiry_fields, timestamp


def render(context):
    import streamlit as st

    st.title("MCP keys")
    zone = browser_timezone(st.context.timezone, st.context.timezone_offset)
    try:
        settings = context.auth("mcp.catalog")
    except PluginError as error:
        st.error(error.message)
        return
    state = settings["status"]
    if state["mode"] == "public":
        st.warning("MCP is public. Enable protected access to require bearer keys.")
    elif state["mode"] == "unavailable":
        st.warning(
            "Protected MCP is unavailable until its authentication provider is ready."
        )
    else:
        st.success("MCP requires a bearer key for every request.")
    if context.can("system.settings.manage"):
        with st.expander("MCP access policy"):
            mode = st.selectbox(
                "MCP access",
                ["public", "protected"],
                index=0 if settings["policy"]["mode"] == "public" else 1,
            )
            if st.button("Save MCP access policy"):
                try:
                    context.auth(
                        "mcp.policy",
                        {"mode": mode, "expected_revision": settings["revision"]},
                    )
                    st.rerun()
                except PluginError as error:
                    st.error(error.message)
    if not state["provider_available"]:
        st.info("Install and enable the MCP authentication plugin to manage keys.")
        return
    try:
        records = context.auth("mcp.list")["keys"]
    except PluginError as error:
        st.error(error.message)
        return
    st.caption(
        "Create a separate key for each client. Keys grant only the selected business permissions."
    )
    generation = st.session_state.get("mcp-draft-generation", 0)
    prefix = f"mcp-key-{generation}"
    with st.container(border=True):
        st.subheader("New MCP key")
        label = st.text_input(
            "Name", value="Unnamed MCP key", max_chars=120, key=f"{prefix}-label"
        )
        catalog = settings["scopes"]
        scopes = st.multiselect(
            "Business permissions",
            list(catalog),
            format_func=lambda s: f"{catalog[s]['title']} ({s})",
            key=f"{prefix}-scopes",
        )
        expiry = expiry_fields(st, prefix, zone=zone)
        if settings["max_expires_at"] is not None:
            st.caption(
                f"Your grant permits keys expiring no later than {timestamp(settings['max_expires_at'], zone)}."
            )
        create = st.button("Generate key", type="primary")
    if create:
        try:
            result = context.auth(
                "mcp.create", {"label": label, "scopes": scopes, "expires_at": expiry}
            )
        except PluginError as error:
            st.error(error.message)
        else:
            st.session_state["created-mcp-key"] = result["token"]
            st.session_state["mcp-draft-generation"] = generation + 1
            st.rerun()
    token = st.session_state.pop("created-mcp-key", None)
    if token:
        st.success("Key created. Copy it now; it cannot be retrieved later.")
        st.code(token, language=None)
        st.code(f"Authorization: Bearer {token}", language=None)
    if st.context.url:
        location = urlsplit(st.context.url)
        st.text_input(
            "MCP URL",
            value=urlunsplit((location.scheme, location.netloc, "/mcp", "", "")),
            disabled=True,
        )
    else:
        st.caption("MCP URL: your application's address followed by /mcp.")
    st.caption(
        "Use HTTPS for remote connections and configure the Authorization header in your MCP client."
    )
    st.subheader("Key records")
    now = time.time()
    st.dataframe(
        [
            {
                "Name": row["label"],
                "Key": row["masked_key"],
                "Permissions": ", ".join(row["scopes"]),
                "Status": "Revoked"
                if row["revoked_at"] is not None
                else "Expired"
                if row["expires_at"] is not None and row["expires_at"] <= now
                else "Active",
                "Created": timestamp(row["created_at"], zone),
                "Expires": timestamp(row["expires_at"], zone),
                "Last used": timestamp(row["last_used"], zone),
            }
            for row in records
        ],
        hide_index=True,
        width="stretch",
    )
    if st.button("Refresh keys"):
        st.rerun()
    active = [row for row in records if row["revoked_at"] is None]
    if active:
        identifier = st.selectbox(
            "Key to revoke",
            [row["id"] for row in active],
            format_func=lambda key: next(
                f"{row['label']} ({key[:8]})" for row in active if row["id"] == key
            ),
        )
        if st.button("Revoke key"):
            try:
                context.auth("mcp.revoke", {"id": identifier})
                st.rerun()
            except PluginError as error:
                st.error(error.message)
    st.caption(
        "To rotate a key, generate a replacement, update the client, then revoke the old key."
    )
