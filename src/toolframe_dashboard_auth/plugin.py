import json
from html import escape
from importlib.resources import files
from urllib.parse import urlsplit

from toolframe_sdk import (
    AuthorizationSpec,
    MethodSpec,
    Plugin,
    PluginDefinition,
    PluginError,
    Requirement,
    Resource,
    ServiceSpec,
)


class DashboardAuth(Plugin):
    async def health(self):
        return {**await super().health(), "capabilities": ["gateway-endpoints-v1"]}

    async def invoke(self, service, method, params):
        endpoints = params.get("endpoints", self.context.endpoints)
        values = {
            "login_url": endpoints.get("login_url", "/_toolframe/auth/login"),
            "session_url": endpoints.get("session_url", "/_toolframe/session"),
            "oidc_providers_url": endpoints.get(
                "oidc_providers_url", "/_toolframe/oidc/providers"
            ),
            "return_to": params.get("return_to", endpoints.get("landing_url", "/")),
        }
        for value in values.values():
            if (
                not isinstance(value, str)
                or not value.startswith("/")
                or value.startswith("//")
                or urlsplit(value).netloc
                or urlsplit(value).fragment
                or any(c in value for c in "\\\r\n\x00")
            ):
                raise PluginError(
                    "gateway_endpoints_invalid", "Login links must be same-origin paths"
                )
        template = files("toolframe_dashboard_auth").joinpath("login.html").read_text()
        for key, value in values.items():
            template = template.replace("{{" + key + "}}", escape(value, quote=True))
            template = template.replace(
                "{{" + key + "_json}}",
                json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e"),
            )
        return {"html": template}


plugin = PluginDefinition(
    id="dashboard-auth",
    kind="provider",
    provider_kind="dashboard-auth",
    factory="toolframe_dashboard_auth.plugin:DashboardAuth",
    authorization=AuthorizationSpec(),
    requires={"auth": Requirement(service="toolframe.auth")},
    services={
        "dashboard-auth.presentation": ServiceSpec(
            methods={"login": MethodSpec(audience="internal", read_only=True)}
        )
    },
    resources=(
        Resource(
            id="connections",
            kind="dashboard.page",
            title="Connected agents",
            required_scopes=("system.auth.self",),
            data={
                "entrypoint": "toolframe_dashboard_auth.connections:render",
                "order": 890,
            },
        ),
        Resource(
            id="users",
            kind="dashboard.page",
            title="User access",
            required_scopes=("system.auth.users",),
            data={"entrypoint": "toolframe_dashboard_auth.users:render", "order": 895},
        ),
        Resource(
            id="passwords",
            kind="dashboard.page",
            title="Access passwords",
            required_scopes=("system.auth.passwords",),
            data={"entrypoint": "toolframe_dashboard_auth.page:render", "order": 900},
        ),
        Resource(
            id="mcp-keys",
            kind="dashboard.page",
            title="MCP keys",
            required_scopes=("system.auth.mcp_keys",),
            data={
                "entrypoint": "toolframe_dashboard_auth.mcp_page:render",
                "order": 910,
            },
        ),
    ),
)
