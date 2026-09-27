"""`garmin-watch-mcp login`: sign in once in a terminal (answering MFA) and save tokens.

The MCP server speaks over stdio and cannot ask for an MFA code, so accounts
with MFA must log in here first. The server then reuses the saved tokens,
which garminconnect refreshes on its own.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from garmin_watch_mcp.config import load_settings
from garmin_watch_mcp.core import GarminError
from garmin_watch_mcp.core.client import GarminClient, is_inline_tokens


def _ask(prompt: str) -> str:
    print(prompt, end="", file=sys.stderr, flush=True)
    return input().strip()


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="garmin-watch-mcp login",
        description="Log in to Garmin Connect and save tokens for the MCP server.",
    )
    parser.add_argument(
        "--print-tokens",
        action="store_true",
        help="also print the token JSON, to use as GARMINTOKENS (e.g. in Docker). Keep it secret.",
    )
    args = parser.parse_args(argv)

    settings = load_settings(require_auth=False)
    if is_inline_tokens(settings.tokenstore):
        print("GARMINTOKENS holds token JSON; unset it or set it to a directory.", file=sys.stderr)
        return 2

    email = settings.email or _ask("Garmin email: ")
    password = settings.password or getpass.getpass("Garmin password: ")
    # If valid tokens are already saved, garminconnect reuses them and skips the password.
    client = GarminClient(
        email,
        password,
        tokenstore=settings.tokenstore,
        is_cn=settings.is_cn,
        prompt_mfa=lambda: _ask("MFA code: "),
    )
    try:
        asyncio.run(client.authenticate())
    except GarminError as exc:
        print(f"Login failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Logged in. Tokens saved to {os.path.expanduser(settings.tokenstore)}", file=sys.stderr)
    if args.print_tokens:
        print(client.export_tokens())
    return 0
