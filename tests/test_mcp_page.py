import time

from streamlit.testing.v1 import AppTest
from test_presentation import widget
from toolframe_sdk import PluginError


class Context:
    def __init__(self, *, available=True, administrator=False):
        self.calls = []
        self.records = []
        self.available = available
        self.administrator = administrator
        self.mode = "public"
        self.fail_create = False

    def can(self, scope):
        return self.administrator if scope == "system.settings.manage" else True

    def auth(self, action, params=None):
        self.calls.append((action, params))
        if action == "mcp.catalog":
            return {
                "scopes": {
                    "notes.read": {"title": "Read notes", "category": "business"}
                },
                "policy": {"mode": self.mode},
                "revision": "revision",
                "status": {"mode": self.mode, "provider_available": self.available},
                "max_expires_at": None,
                "mcp_path": "/mcp",
            }
        if action == "mcp.list":
            return {"keys": self.records}
        if action == "mcp.create":
            if self.fail_create:
                raise PluginError("forbidden", "Cannot delegate those permissions")
            self.records.append(
                {
                    "id": "key-1",
                    **params,
                    "created_at": time.time(),
                    "last_used": None,
                    "revoked_at": None,
                    "masked_key": "tf_mcp_•••• (key-1)",
                }
            )
            return {"token": "tf_mcp_" + "a" * 43, "key": self.records[-1]}
        if action == "mcp.revoke":
            self.records[0]["revoked_at"] = time.time()
            return {}
        if action == "mcp.policy":
            assert params["expected_revision"] == "revision"
            self.mode = params["mode"]
            return {}
        raise AssertionError(action)


def app(context):
    from toolframe_dashboard_auth.mcp_page import render

    render(context)


def test_create_copy_once_and_revoke():
    context = Context()
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run(timeout=60)
    assert not ui.exception
    assert not any(button.label == "Save MCP access policy" for button in ui.button)
    assert widget(ui, "multiselect", "Business permissions").value == []
    widget(ui, "text_input", "Name").set_value("Laptop").run()
    widget(ui, "multiselect", "Business permissions").select("notes.read").run()
    widget(ui, "button", "Generate key").click().run()
    assert not ui.exception
    assert [payload for action, payload in context.calls if action == "mcp.create"] == [
        {"label": "Laptop", "scopes": ["notes.read"], "expires_at": None}
    ]
    token = "tf_mcp_" + "a" * 43
    assert ui.code[0].value == token
    assert ui.code[1].value == "Authorization: Bearer " + token
    assert "created-mcp-key" not in ui.session_state
    ui.run()
    assert not ui.code
    widget(ui, "button", "Revoke key").click().run()
    assert not ui.exception and context.records[0]["revoked_at"] is not None


def test_failed_create_keeps_draft_and_shows_no_secret():
    context = Context()
    context.fail_create = True
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    widget(ui, "text_input", "Name").set_value("Keep this name").run()
    widget(ui, "multiselect", "Business permissions").select("notes.read").run()
    widget(ui, "checkbox", "Set expiry").set_value(True).run()
    widget(ui, "button", "Generate key").click().run()
    assert not ui.exception and not ui.code
    assert "Cannot delegate" in ui.error[0].value
    assert widget(ui, "text_input", "Name").value == "Keep this name"
    assert widget(ui, "checkbox", "Set expiry").value
    assert not context.records


def test_missing_provider_keeps_policy_recovery_available():
    context = Context(available=False, administrator=True)
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    assert not ui.exception
    assert not any(button.label == "Generate key" for button in ui.button)
    widget(ui, "selectbox", "MCP access").select("protected").run()
    widget(ui, "button", "Save MCP access policy").click().run()
    assert context.mode == "protected"
    assert not any(action == "mcp.create" for action, _ in context.calls)
