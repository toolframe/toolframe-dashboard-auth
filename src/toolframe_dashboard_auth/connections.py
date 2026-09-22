"""Own-account delegation management backed by the shared authority."""

import time

from toolframe_sdk import PluginError


def render(context):
    import streamlit as st

    st.title("Connected agents")
    st.caption(
        "Each connection has its own permissions. Revoking an agent keeps your Dashboard session signed in."
    )
    try:
        records = context.auth("grants")["grants"]
    except PluginError as error:
        st.info(error.message)
        return
    if not records:
        st.info(
            "No agents connected. Add this application's MCP URL in your agent to authorize a connection."
        )
    for record in records:
        with st.container(border=True):
            st.subheader(record["client_name"])
            st.write(record["resource"])
            st.write("Permissions: " + ", ".join(record["scopes"]))
            if record["revoked_at"] is not None:
                st.caption("Revoked")
            elif record["expires_at"] <= time.time():
                st.caption("Expired")
            elif st.button("Revoke access", key="revoke-" + record["id"]):
                try:
                    context.auth("revoke_grant", {"id": record["id"]})
                    st.rerun()
                except PluginError as error:
                    st.error(error.message)
    if st.button("Refresh connections"):
        st.rerun()
