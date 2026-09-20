from streamlit.testing.v1 import AppTest
from toolframe_sdk import RuntimeContext

from toolframe_dashboard_auth.plugin import DashboardAuth, plugin


async def test_login_is_password_only_and_management_page_is_scoped():
    provider = DashboardAuth(
        RuntimeContext(None, plugin_id="dashboard-auth", generation="test")
    )
    html = (await provider.invoke("dashboard-auth.presentation", "login", {}))["html"]
    assert 'name="password"' in html
    assert 'name="username"' not in html and 'name="token"' not in html
    assert 'action="/_toolframe/auth/login"' in html
    assert plugin.resources[0].required_scopes == ("system.auth.passwords",)
    assert all(
        method.audience == "internal"
        for service in plugin.services.values()
        for method in service.methods.values()
    )


class Context:
    def __init__(self):
        self.calls = []

    def can(self, scope):
        return scope != "system.settings.manage"

    def auth(self, action, params=None):
        self.calls.append((action, params))
        if action == "catalog":
            return {
                "scopes": {
                    "notes.read": {
                        "owner": "notes",
                        "title": "Read",
                        "category": "business",
                    },
                    "system.auth.passwords": {
                        "owner": "system",
                        "title": "Manage passwords",
                        "category": "system",
                    },
                },
                "policy": {"mode": "public", "local_control": True},
                "revision": "revision",
            }
        if action == "list":
            return {"credentials": []}
        if action == "create":
            return {"password": "one-time-generated-example"}
        raise AssertionError(action)


def app(context):
    from toolframe_dashboard_auth.page import render

    render(context)


def test_create_defaults_exclude_system_scopes_and_reveals_secret_once():
    context = Context()
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    assert not ui.exception
    assert all(not item.value for item in ui.multiselect)
    assert not any(button.label == "Save access policy" for button in ui.button)
    next(item for item in ui.text_input if item.label == "Name").set_value("Colleague")
    next(
        button for button in ui.button if button.label == "Create password"
    ).click().run()
    assert not ui.exception
    action, payload = next(call for call in context.calls if call[0] == "create")
    assert action == "create" and payload == {
        "label": "Colleague",
        "scopes": [],
        "all_business": True,
        "expires_at": None,
        "password": None,
        "expected_revision": "revision",
    }
    assert ui.code[0].value == "one-time-generated-example"
    ui.run()
    assert not ui.code


def test_expiry_edit_revocation_and_record_timestamps():
    import time

    class Existing(Context):
        def __init__(self):
            super().__init__()
            self.record = {
                "id": "ab" * 16,
                "label": "Existing",
                "scopes": ["notes.read"],
                "all_business": False,
                "created_at": time.time(),
                "expires_at": None,
                "revoked_at": None,
                "last_login": time.time(),
                "last_used": time.time(),
            }

        def auth(self, action, params=None):
            if action == "list":
                return {"credentials": [self.record.copy()]}
            if action in {"update", "revoke"}:
                self.calls.append((action, params))
                if action == "update":
                    self.record.update(params)
                else:
                    self.record["revoked_at"] = time.time()
                return self.record.copy()
            return super().auth(action, params)

    context = Existing()
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    assert not ui.exception
    assert {"created_at", "last_login", "last_used", "expires_at"} <= set(
        ui.dataframe[0].value.columns
    )
    next(
        item for item in ui.checkbox if item.key == context.record["id"] + "-limited"
    ).set_value(True)
    next(
        button for button in ui.button if button.label == "Save password grant"
    ).click().run()
    assert not ui.exception
    assert time.time() < context.record["expires_at"] < time.time() + 8 * 86400
    next(
        button for button in ui.button if button.label == "Revoke password"
    ).click().run()
    assert not ui.exception
    assert context.record["revoked_at"] is not None
    assert any("Revoked" in message.value for message in ui.info)
    assert not any(button.label == "Save password grant" for button in ui.button)
