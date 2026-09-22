"""Administration of admitted federated users; no provider tokens enter the UI."""

from toolframe_sdk import PluginError


def render(context):
    import streamlit as st

    st.title("User access")
    st.caption(
        "External identities are admitted through application configuration. Manage their local permissions here after their first sign-in."
    )
    try:
        settings = context.auth("user_catalog")
        users = context.auth("users")["users"]
    except PluginError as error:
        st.error(error.message)
        return
    if not users:
        st.info("No admitted users have signed in yet.")
        return
    by_id = {user["id"]: user for user in users}
    identifier = st.selectbox(
        "User", list(by_id), format_func=lambda key: by_id[key]["label"]
    )
    user = by_id[identifier]
    scopes = st.multiselect(
        "Permissions",
        list(settings["scopes"]),
        default=[scope for scope in user["scopes"] if scope in settings["scopes"]],
        key="user-scopes-" + identifier,
    )
    disabled = st.checkbox(
        "Disable user", value=bool(user["disabled"]), key="user-disabled-" + identifier
    )
    if st.button("Save user access"):
        try:
            context.auth(
                "user_update",
                {
                    "id": identifier,
                    "scopes": scopes,
                    "disabled": disabled,
                    "expires_at": user["expires_at"],
                },
            )
            st.success("User access saved.")
        except PluginError as error:
            st.error(error.message)
    st.caption(
        "Permission reductions affect existing connections. Disabling a user also revokes their sessions and agent grants."
    )
