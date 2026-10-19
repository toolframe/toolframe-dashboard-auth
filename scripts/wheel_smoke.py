"""Check installed plugin metadata and packaged login HTML outside the checkout."""

import asyncio
import json
import sys
import tomllib
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path

import toolframe_sdk
from toolframe_sdk import RuntimeContext

import toolframe_dashboard_auth
from toolframe_dashboard_auth.page import render
from toolframe_dashboard_auth.plugin import DashboardAuth

project_root = Path(__file__).resolve().parents[1]
expected_version = tomllib.loads((project_root / "pyproject.toml").read_text())[
    "project"
]["version"]
installed = distribution("toolframe-dashboard-auth")
assert installed.version == expected_version
assert distribution("toolframe-sdk").version == "0.4.0"
for module in (toolframe_dashboard_auth, toolframe_sdk):
    installed_path = Path(module.__file__).resolve()
    assert installed_path.is_relative_to(Path(sys.prefix).resolve()), installed_path
    print(f"Installed module: {installed_path}")
assert (
    not json.loads(installed.read_text("direct_url.json"))
    .get("dir_info", {})
    .get("editable", False)
)
assert installed.metadata["License-Expression"] == "Apache-2.0"
for name in ("LICENSE", "NOTICE"):
    license_file = next(
        path
        for path in installed.files
        if str(path).endswith(f".dist-info/licenses/{name}")
    )
    assert (
        installed.locate_file(license_file).read_bytes()
        == (project_root / name).read_bytes()
    )

entrypoint = next(
    item
    for item in installed.entry_points
    if item.group == "toolframe.plugins" and item.name == "dashboard-auth"
)
plugin = entrypoint.load()
assert plugin.id == "dashboard-auth"
assert next(
    page for page in plugin.resources if page.id == "passwords"
).required_scopes == ("system.auth.passwords",)
assert next(
    page for page in plugin.resources if page.id == "connections"
).required_scopes == ("system.auth.self",)
assert callable(render)
provider = DashboardAuth(
    RuntimeContext(None, plugin_id="dashboard-auth", generation="ci")
)
result = asyncio.run(provider.invoke("dashboard-auth.presentation", "login", {}))
html = files("toolframe_dashboard_auth").joinpath("login.html").read_text()
assert result["html"] == html
assert 'name="password"' in html and 'action="/_toolframe/auth/login"' in html
assert 'name="username"' not in html and 'name="token"' not in html
print(
    f"Wheel smoke passed: version {installed.version}, entry point, login HTML, licenses"
)
