from importlib.resources import files

from toolframe_sdk import (
    AuthorizationSpec,
    MethodSpec,
    Plugin,
    PluginDefinition,
    Requirement,
    Resource,
    ServiceSpec,
)


class DashboardAuth(Plugin):
    async def invoke(self, service, method, params):
        return {
            "html": files("toolframe_dashboard_auth").joinpath("login.html").read_text()
        }


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
