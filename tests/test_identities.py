"""Account pages issue bounded authority operations through the public facade."""

import time

from streamlit.testing.v1 import AppTest


class Context:
    def __init__(self):
        self.calls = []
        self.grant = {
            "id": "grant",
            "client_name": "Agent",
            "resource": "https://app.example/mcp",
            "scopes": ["notes.read"],
            "expires_at": time.time() + 3600,
            "revoked_at": None,
        }

    def auth(self, action, params=None):
        self.calls.append((action, params))
        if action == "grants":
            return {"grants": [self.grant]}
        if action == "revoke_grant":
            self.grant["revoked_at"] = time.time()
            return {"revoked": True}
        if action == "user_catalog":
            return {"scopes": {"notes.read": {"title": "Read notes"}}}
        if action == "users":
            return {
                "users": [
                    {
                        "id": "user",
                        "label": "Person",
                        "scopes": ["notes.read", "removed.scope"],
                        "disabled": False,
                        "expires_at": None,
                    }
                ]
            }
        if action == "user_update":
            return {"user": params}
        raise AssertionError(action)


def connections(context):
    from toolframe_dashboard_auth.connections import render

    render(context)


def users(context):
    from toolframe_dashboard_auth.users import render

    render(context)


def test_revoke_connection_does_not_sign_out():
    context = Context()
    ui = AppTest.from_function(connections, args=(context,)).run()
    assert not ui.exception
    next(
        button for button in ui.button if button.label == "Revoke access"
    ).click().run()
    assert not ui.exception and ("revoke_grant", {"id": "grant"}) in context.calls
    assert any(caption.value == "Revoked" for caption in ui.caption)
    assert all(action != "logout" for action, _ in context.calls)


def test_user_edit_handles_removed_scopes_and_disables_explicitly():
    context = Context()
    ui = AppTest.from_function(users, args=(context,)).run()
    assert not ui.exception and ui.multiselect[0].value == ["notes.read"]
    ui.checkbox[0].check()
    ui.button[0].click().run()
    assert not ui.exception
    assert (
        "user_update",
        {"id": "user", "scopes": ["notes.read"], "disabled": True, "expires_at": None},
    ) in context.calls
