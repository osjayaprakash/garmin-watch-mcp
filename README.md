# garmin-watch-mcp

<!-- mcp-name: io.github.osjayaprakash/garmin-watch-mcp -->

[![CI](https://github.com/osjayaprakash/garmin-watch-mcp/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/osjayaprakash/garmin-watch-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/garmin-watch-mcp)](https://pypi.org/project/garmin-watch-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/garmin-watch-mcp)](https://pypi.org/project/garmin-watch-mcp/)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-2496ED?logo=docker&logoColor=white)](https://github.com/osjayaprakash/garmin-watch-mcp/pkgs/container/garmin-watch-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/osjayaprakash/garmin-watch-mcp/blob/master/LICENSE)

An MCP server that gives Claude (or any MCP client) read-only access to the health and
activity data your Garmin watch syncs to Garmin Connect: daily summaries, sleep, heart
rate, stress, Body Battery, HRV, training readiness, activities and devices. It talks to
Garmin Connect through [python-garminconnect](https://github.com/cyberjunky/python-garminconnect),
wrapped in a small async client (`garmin_watch_mcp.core`).

## Tools

| Tool | Returns |
|---|---|
| `get_daily_summary` | Steps, distance, calories, floors, heart rate, stress, Body Battery, intensity minutes, SpO2 |
| `get_sleep` | Sleep stages, score, start/end, overnight HRV and resting heart rate |
| `get_heart_rate` | Resting/min/max heart rate and hourly min/avg/max |
| `get_stress` | Average/max stress and hourly min/avg/max |
| `get_body_battery` | Charged, drained, highest, lowest and latest level per day (up to 31 days) |
| `get_hrv` | Last-night and weekly HRV, baseline and status |
| `get_training_readiness` | Latest readiness score and its factors |
| `list_activities` | Recent activities, or those in a date range, newest first |
| `get_activity` | One activity's duration, distance, pace, heart rate, elevation, training effect |
| `list_devices` | Garmin devices on the account |

Day-based tools take an optional `date` (`YYYY-MM-DD`, `today` or `yesterday`), which
defaults to today in the server's local time zone. Durations are seconds, distances
metres and speeds m/s. Garmin's raw responses are large, so each tool keeps a curated set
of fields and summarises intraday samples by hour (UTC).

## Setup

For a step-by-step guide, including MFA and troubleshooting, see the
[installation guide](https://garmin-watch-mcp.readthedocs.io/en/latest/install/).
Full documentation is at <https://garmin-watch-mcp.readthedocs.io>.

You need a Garmin Connect account that your watch syncs to.

```bash
git clone https://github.com/osjayaprakash/garmin-watch-mcp.git && cd garmin-watch-mcp
uv sync
uv run garmin-watch-mcp login   # once: asks for email, password and MFA code, saves tokens
```

`login` saves OAuth tokens to `~/.garminconnect`; the server reuses and refreshes them, so
it needs no password afterwards. Without MFA you can skip `login` and set
`GARMIN_EMAIL`/`GARMIN_PASSWORD` instead.

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `GARMIN_EMAIL` | without saved tokens | | Garmin Connect account email |
| `GARMIN_PASSWORD` | without saved tokens | | Garmin Connect account password |
| `GARMINTOKENS` | no | `~/.garminconnect` | Token directory, or the token JSON itself |
| `GARMIN_IS_CN` | no | `false` | `true` for Garmin Connect China (garmin.cn) accounts |

### Run from PyPI

No clone needed; [uv](https://docs.astral.sh/uv/) fetches and runs the published package:

```bash
uvx garmin-watch-mcp login   # once
uvx garmin-watch-mcp
```

In a client config, use `"command": "uvx", "args": ["garmin-watch-mcp"]`.

### Run with Docker

The server speaks MCP over stdio, so keep `-i`. Pass the tokens from
`garmin-watch-mcp login --print-tokens` as `GARMINTOKENS`:

```bash
docker run -i --rm -e GARMINTOKENS ghcr.io/osjayaprakash/garmin-watch-mcp:latest
```

Or mount a token directory:
`-v ~/.garminconnect:/home/app/.garminconnect`. In a client config, use
`"command": "docker"` with those arguments, and pass the variables through the client's
`env` block.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "garmin": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/garmin-watch-mcp", "run", "garmin-watch-mcp"]
    }
  }
}
```

Add an `env` block with `GARMIN_EMAIL`/`GARMIN_PASSWORD` if you didn't run `login`.

### Claude Code

```bash
claude mcp add garmin -- uv --directory /absolute/path/to/garmin-watch-mcp run garmin-watch-mcp
```

## Langfuse tracing (optional)

Each tool call becomes a Langfuse trace, with a child span for the Garmin Connect call.
Install the extra and set the keys:

```bash
uv sync --extra langfuse
```

In the server command, use `run --extra langfuse garmin-watch-mcp` instead of
`run garmin-watch-mcp`.

| Variable | Meaning |
|---|---|
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Tracing is on only when both are set |
| `LANGFUSE_BASE_URL` | Langfuse URL for self-hosted or regional instances (default: Langfuse Cloud) |
| `LANGFUSE_CAPTURE_DATA` | `true` to include tool inputs, outputs and error messages. Default `false` |

**Privacy:** sleep, heart rate and activity data are health data. By default, traces hold
only tool names, timings and error class names. Setting `LANGFUSE_CAPTURE_DATA=true` sends
the data itself to your Langfuse instance; only do that with an instance you trust, such
as a self-hosted one.

## Development

```bash
uv sync
uv run pytest            # offline suite
uv run pytest -m live    # hits the real API; needs saved tokens or GARMIN_EMAIL/PASSWORD
uv run ruff check src tests && uv run ruff format --check src tests
```

## Releasing

Bump `version` in `pyproject.toml` and `server.json`, then push a matching tag
(`git tag v0.1.0 && git push --tags`). That publishes:

| Channel | Workflow | Needs |
|---|---|---|
| PyPI | `pypi.yml` | `PYPI_API_TOKEN` repository secret |
| Docker image on ghcr.io | `docker.yml` | nothing (uses `GITHUB_TOKEN`) |
| Official MCP Registry | `mcp-registry.yml` | nothing (GitHub OIDC); waits for PyPI and ghcr.io |
| Read the Docs | `.readthedocs.yaml` | import the repo once at readthedocs.org |

## License

[MIT](https://github.com/osjayaprakash/garmin-watch-mcp/blob/master/LICENSE)

Not affiliated with or endorsed by Garmin. Garmin Connect has no public personal-data API;
this uses the same unofficial endpoints as the Garmin Connect app and may break when
Garmin changes them.
