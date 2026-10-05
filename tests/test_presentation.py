import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest
from toolframe_sdk import PluginError, RuntimeContext

from toolframe_dashboard_auth.page import (
    browser_timezone,
    expiry_after,
    timestamp,
    unnamed_label,
)
from toolframe_dashboard_auth.plugin import DashboardAuth, plugin


async def test_login_supports_password_and_oidc_with_scoped_management_pages():
    provider = DashboardAuth(
        RuntimeContext(None, plugin_id="dashboard-auth", generation="test")
    )
    html = (await provider.invoke("dashboard-auth.presentation", "login", {}))["html"]
    assert 'name="password"' in html
    assert 'name="username"' not in html and 'name="token"' not in html
    assert 'action="/_toolframe/auth/login"' in html
    assert "/_toolframe/oidc/providers" in html
    scopes = {page.id: page.required_scopes for page in plugin.resources}
    assert scopes["passwords"] == ("system.auth.passwords",)
    assert scopes["users"] == ("system.auth.users",)
    assert scopes["connections"] == ("system.auth.self",)
    assert all(
        method.audience == "internal"
        for service in plugin.services.values()
        for method in service.methods.values()
    )


class Context:
    def __init__(self):
        self.calls = []
        self.records = []
        self.fail_create = False
        self.settings_manager = False
        self.policy = {
            "mode": "public",
            "local_control": True,
            "failure_mode": "closed",
        }
        self.policy_options = {"failure_modes": ["closed", "public"]}

    def can(self, scope):
        return self.settings_manager or scope != "system.settings.manage"

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
                "policy": self.policy.copy(),
                "policy_options": self.policy_options,
                "entrances": {
                    "dashboard": {
                        "mode": self.policy["mode"],
                        "configured": self.policy["mode"],
                    },
                    "mcp": {"mode": "public", "configured": "public"},
                    "actor": "local",
                    "declared_public_api": ["/api/notes/notes.notes/list_notes"],
                },
                "revision": "revision",
            }
        if action == "policy":
            self.policy.update(
                {
                    key: value
                    for key, value in params.items()
                    if key != "expected_revision"
                }
            )
            return {"mode": self.policy["mode"]}
        if action == "list":
            return {"credentials": [record.copy() for record in self.records]}
        if action == "create":
            if self.fail_create:
                raise PluginError("password_conflict", "Password already in use")
            self.records.append(
                {
                    "id": str(len(self.records) + 1),
                    **{
                        k: params[k]
                        for k in ("label", "scopes", "all_business", "expires_at")
                    },
                    "created_at": time.time(),
                    "revoked_at": None,
                    "last_login": None,
                    "last_used": None,
                }
            )
            return {"password": None}
        if action in {"update", "revoke"}:
            record = next(
                record for record in self.records if record["id"] == params["id"]
            )
            if action == "update":
                record.update(params)
            else:
                record["revoked_at"] = time.time()
            return record.copy()
        raise AssertionError(action)


def app(context):
    from toolframe_dashboard_auth.page import render

    render(context)


def widget(ui, kind, label):
    return next(item for item in getattr(ui, kind) if item.label == label)


def test_access_entrances_and_failure_policy_can_be_reviewed_and_saved():
    context = Context()
    context.settings_manager = True
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    assert not ui.exception
    assert any("**MCP:** public" in item.value for item in ui.markdown)
    assert any("/api/notes/notes.notes/list_notes" == item.value for item in ui.caption)
    assert any("Current caller: local" in item.value for item in ui.caption)
    failure = widget(ui, "selectbox", "When Dashboard authentication is unavailable")
    assert failure.value == "closed"
    widget(ui, "selectbox", "Dashboard access").select("protected").run()
    widget(ui, "selectbox", "When Dashboard authentication is unavailable").select(
        "public"
    ).run()
    assert any(
        "anonymous visitors receive all business scopes" in item.value
        for item in ui.warning
    )
    widget(ui, "button", "Save access policy").click().run()
    assert not ui.exception
    assert (
        "policy",
        {
            "mode": "protected",
            "local_control": True,
            "failure_mode": "public",
            "expected_revision": "revision",
        },
    ) in context.calls


def test_older_core_does_not_offer_an_unsupported_failure_policy_control():
    context = Context()
    context.settings_manager = True
    context.policy_options = {}
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    assert not any(
        item.label == "When Dashboard authentication is unavailable"
        for item in ui.selectbox
    )
    widget(ui, "button", "Save access policy").click().run()
    assert "failure_mode" not in next(
        params for action, params in context.calls if action == "policy"
    )


def test_create_defaults_exclude_system_scopes_and_reveals_secret_once():
    context = Context()
    # Cold pandas/PyArrow native imports need extra time; later runs still use 15s.
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run(timeout=60)
    assert not ui.exception
    assert all(not item.value for item in ui.multiselect)
    assert not any(button.label == "Save access policy" for button in ui.button)
    assert widget(ui, "text_input", "Name").value == "Unnamed password"
    suggested = widget(ui, "text_input", "Password (8–32 characters)").proto.placeholder
    assert len(suggested) == 32
    assert not ui.date_input and not ui.time_input and not ui.number_input
    assert not any(item.label == "Generate a random password" for item in ui.checkbox)
    widget(ui, "text_input", "Name").set_value("Colleague").run()
    assert (
        widget(ui, "text_input", "Password (8–32 characters)").proto.placeholder
        == suggested
    )
    widget(ui, "button", "Create password").click().run()
    assert not ui.exception
    action, payload = next(call for call in context.calls if call[0] == "create")
    assert action == "create" and payload == {
        "label": "Colleague",
        "scopes": [],
        "all_business": True,
        "expires_at": None,
        "password": suggested,
        "expected_revision": "revision",
    }
    assert ui.code[0].value == suggested
    assert "Copy it now" in ui.success[0].value
    assert (
        widget(ui, "text_input", "Password (8–32 characters)").proto.placeholder
        != suggested
    )
    ui.run()
    assert not ui.code


@pytest.mark.parametrize(
    "unit,seconds",
    [("Minutes", 120), ("Hours", 7200), ("Days", 172800), ("Weeks", 1209600)],
)
def test_relative_expiry_reacts_immediately_and_uses_save_time(unit, seconds):
    context = Context()
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    widget(ui, "checkbox", "Set expiry").set_value(True).run()
    assert widget(ui, "number_input", "Expire after").value == 1
    widget(ui, "number_input", "Expire after").set_value(2).run()
    widget(ui, "selectbox", "Unit").select(unit).run()
    assert any("Expires on" in item.value for item in ui.caption)
    before = time.time()
    widget(ui, "button", "Create password").click().run()
    assert not ui.exception
    expiry = context.records[0]["expires_at"]
    assert before + seconds <= expiry <= time.time() + seconds
    assert context.records[0]["label"] == "Unnamed password"
    assert widget(ui, "text_input", "Name").value == "Unnamed password 2"


def test_toggle_hides_expiry_and_submits_no_expiry():
    context = Context()
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    widget(ui, "checkbox", "Set expiry").set_value(True).run()
    widget(ui, "checkbox", "Set expiry").set_value(False).run()
    assert not ui.number_input and not ui.selectbox
    assert not any("Expires on" in item.value for item in ui.caption)
    widget(ui, "text_input", "Name").set_value(" ")
    widget(ui, "button", "Create password").click().run()
    assert context.records[0]["expires_at"] is None
    assert context.records[0]["label"] == "Unnamed password"


def test_custom_password_validation_and_failure_preserve_draft():
    context = Context()
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    password = widget(ui, "text_input", "Password (8–32 characters)")
    suggested = password.proto.placeholder
    assert password.proto.max_chars == 32
    password.set_value("short")
    widget(ui, "button", "Create password").click().run()
    assert "8–32" in ui.error[0].value
    assert not any(action == "create" for action, _ in context.calls)
    assert (
        widget(ui, "text_input", "Password (8–32 characters)").proto.placeholder
        == suggested
    )
    widget(ui, "text_input", "Password (8–32 characters)").set_value("eightchr")
    context.fail_create = True
    widget(ui, "button", "Create password").click().run()
    assert ui.error[0].value == "Password already in use"
    assert widget(ui, "text_input", "Password (8–32 characters)").value == "eightchr"
    assert (
        widget(ui, "text_input", "Password (8–32 characters)").proto.placeholder
        == suggested
    )
    context.fail_create = False
    widget(ui, "button", "Create password").click().run()
    assert not ui.exception
    assert ui.code[0].value == "eightchr"
    assert [
        params["password"] for action, params in context.calls if action == "create"
    ] == ["eightchr", "eightchr"]


@pytest.mark.parametrize(
    "start,amount,expected",
    [
        ("2026-01-31", 1, "2026-02-28"),
        ("2028-01-31", 1, "2028-02-29"),
        ("2026-12-31", 2, "2027-02-28"),
        ("2026-01-31", 2, "2026-03-31"),
    ],
)
def test_calendar_month_expiry_preserves_time_and_clamps_month_end(
    start, amount, expected
):
    now = datetime.fromisoformat(start + "T14:23:45+00:00")
    actual = datetime.fromtimestamp(expiry_after(now, amount, "Months"), UTC)
    assert actual.isoformat() == expected + "T14:23:45+00:00"


def test_default_name_skips_existing_names_including_revoked_records():
    assert (
        unnamed_label(
            [
                {"label": "Unnamed password"},
                {"label": "Unnamed password 2", "revoked_at": 1},
                {"label": "Unnamed password 3"},
                {"label": "Colleague"},
            ]
        )
        == "Unnamed password 4"
    )


def test_local_timezone_formatting_and_elapsed_duration_across_dst():
    hong_kong = browser_timezone("Asia/Hong_Kong", 0)
    value = datetime(2026, 9, 20, 14, 18, 45, tzinfo=UTC).timestamp()
    assert timestamp(value, hong_kong) == "2026-09-20 22:18:45 HKT"
    assert timestamp(None, hong_kong) == "—"
    assert timestamp(value, browser_timezone("invalid/zone", -480)).endswith(
        "22:18:45 UTC+08:00"
    )
    assert browser_timezone(None, None) is UTC
    new_york = ZoneInfo("America/New_York")
    spring = datetime(2026, 3, 8, 1, 30, tzinfo=new_york)
    assert expiry_after(spring, 2, "Hours") - spring.timestamp() == 7200
    february = datetime(2026, 2, 20, 14, 30, tzinfo=new_york)
    march = datetime.fromtimestamp(expiry_after(february, 1, "Months"), new_york)
    assert march.isoformat() == "2026-03-20T14:30:00-04:00"


def test_duration_and_unit_share_a_row_and_use_browser_timezone(monkeypatch):
    from streamlit.runtime.context import ContextProxy

    monkeypatch.setattr(ContextProxy, "timezone", property(lambda _: "Asia/Hong_Kong"))
    ui = AppTest.from_function(app, args=(Context(),), default_timeout=15).run()
    widget(ui, "checkbox", "Set expiry").set_value(True).run()
    assert not ui.exception
    assert len(ui.columns) == 2
    assert ui.columns[0].number_input[0].label == "Expire after"
    assert ui.columns[1].selectbox[0].label == "Unit"
    assert next(
        item.value for item in ui.caption if item.value.startswith("Expires on")
    ).endswith(" HKT")


def test_expiry_edit_revocation_and_record_timestamps():
    context = Context()
    record = {
        "id": "ab" * 16,
        "label": "Existing",
        "scopes": ["notes.read"],
        "all_business": False,
        "created_at": time.time(),
        "expires_at": time.time() + 3600,
        "revoked_at": None,
        "last_login": time.time(),
        "last_used": time.time(),
    }
    context.records = [record]
    ui = AppTest.from_function(app, args=(context,), default_timeout=15).run()
    assert not ui.exception
    assert {"created_at", "last_login", "last_used", "expires_at"} <= set(
        ui.dataframe[0].value.columns
    )
    assert widget(ui, "number_input", "Expire after").value is None
    original_expiry = record["expires_at"]
    widget(ui, "button", "Save password grant").click().run()
    assert not ui.exception
    assert record["expires_at"] == original_expiry
    widget(ui, "number_input", "Expire after").set_value(1).run()
    widget(ui, "selectbox", "Unit").select("Hours").run()
    widget(ui, "button", "Save password grant").click().run()
    assert time.time() + 3590 < record["expires_at"] <= time.time() + 3600
    saved_expiry = record["expires_at"]
    assert widget(ui, "number_input", "Expire after").value is None
    widget(ui, "button", "Save password grant").click().run()
    assert record["expires_at"] == saved_expiry
    next(
        item
        for item in ui.checkbox
        if not item.key.startswith("new-") and item.label == "Set expiry"
    ).set_value(False).run()
    assert not ui.number_input
    widget(ui, "button", "Save password grant").click().run()
    assert record["expires_at"] is None
    widget(ui, "button", "Revoke password").click().run()
    assert not ui.exception
    assert record["revoked_at"] is not None
    assert any("Revoked" in message.value for message in ui.info)
    assert not any(button.label == "Save password grant" for button in ui.button)
