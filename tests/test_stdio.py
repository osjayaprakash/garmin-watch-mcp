"""Run the real entry point as a subprocess: proves nothing but MCP frames reach stdout."""

import sys

from mcp import Client, StdioServerParameters

from tests.test_server import TOOLS

ENV = {
    "GARMIN_EMAIL": "nobody@example.com",
    "GARMIN_PASSWORD": "unused",
    "GARMINTOKENS": "/nonexistent/garmin-tokens",
    "PATH": "",
}


async def test_stdio_server_starts_and_lists_tools():
    params = StdioServerParameters(command=sys.executable, args=["-m", "garmin_watch_mcp"], env=ENV)
    async with Client(params) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools.tools} == TOOLS
