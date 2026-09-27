# Installing garmin-watch-mcp

This guide takes you from nothing to asking Claude "how did I sleep last night?". It
takes about 10 minutes.

## 1. Prerequisites

- **A Garmin watch** that syncs to Garmin Connect through the Garmin Connect app.
- **The Garmin Connect account** it syncs to (email and password; MFA is fine).
- **[uv](https://docs.astral.sh/uv/)**, which installs Python 3.12+ and the dependencies
  for you:

  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # or, with Homebrew
  brew install uv
  ```

  ```powershell
  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

- **An MCP client**, such as Claude Desktop or Claude Code.

## 2. Download and install

```bash
git clone https://github.com/osjayaprakash/garmin-watch-mcp.git
cd garmin-watch-mcp
uv sync
```

Note the full path of this folder; you'll need it below:

```bash
pwd
```

## 3. Log in once

```bash
uv run garmin-watch-mcp login
```

It asks for your email, password and, if the account uses MFA, the code Garmin sends
you. It then saves OAuth tokens to `~/.garminconnect` (readable only by you). The server
reuses and refreshes these tokens, so it never needs your password or an MFA code.

To keep the tokens elsewhere, set `GARMINTOKENS` to a directory, both here and in the
client config below.

If your account doesn't use MFA you may skip this step and pass `GARMIN_EMAIL` and
`GARMIN_PASSWORD` to the server instead; it then logs in on the first tool call.

## 4. Check it works

```bash
uv run pytest -m live -q
```

`1 passed` means the server can log in and read data. If it fails, the error message
tells you what to fix; see [Troubleshooting](#troubleshooting).

## 5. Connect your client

### Claude Desktop

1. Find the full path to `uv`. Claude Desktop doesn't always see your shell's `PATH`, so
   use the absolute path:

   ```bash
   which uv        # macOS / Linux, e.g. /Users/you/.local/bin/uv
   where uv        # Windows
   ```

2. Open the config file (*Settings* → *Developer* → *Edit Config*), or open it directly:

   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

3. Add the server under `mcpServers`, keeping any servers already there:

   ```json
   {
     "mcpServers": {
       "garmin": {
         "command": "/Users/you/.local/bin/uv",
         "args": ["--directory", "/Users/you/garmin-watch-mcp", "run", "garmin-watch-mcp"]
       }
     }
   }
   ```

   If you skipped `login`, add
   `"env": {"GARMIN_EMAIL": "you@example.com", "GARMIN_PASSWORD": "your-password"}`.

   On Windows, double every backslash in paths, for example
   `"C:\\Users\\you\\garmin-watch-mcp"`.

4. Quit Claude Desktop completely and reopen it. The `garmin` tools should appear in the
   tools menu.

### Claude Code

```bash
claude mcp add garmin -- uv --directory /Users/you/garmin-watch-mcp run garmin-watch-mcp
```

This adds the server to the current project only. Add `--scope user` after `add` to make
it available in every project. Check it with `claude mcp list`.

### Docker

Print the tokens once and hand them to the container as `GARMINTOKENS`:

```bash
export GARMINTOKENS="$(uv run garmin-watch-mcp login --print-tokens)"
docker run -i --rm -e GARMINTOKENS ghcr.io/osjayaprakash/garmin-watch-mcp:latest
```

Tokens passed this way can't be written back after a refresh; if calls start failing
with a login error weeks later, run the command again. Mounting the token directory
(`-v ~/.garminconnect:/home/app/.garminconnect`) avoids that.

### Other MCP clients

Run this command; it speaks MCP over stdio:

```bash
uv --directory /path/to/garmin-watch-mcp run garmin-watch-mcp
```

## 6. Try it

Ask Claude:

- "How did I sleep last night?"
- "What was my resting heart rate and Body Battery this week?"
- "Summarise my runs from the last two weeks."
- "Am I ready to train hard today?"

Data appears only after the watch syncs, so today's numbers may lag until you open the
Garmin Connect app.

## Optional: Langfuse tracing

To send a trace of each tool call to [Langfuse](https://langfuse.com):

1. Install the extra: `uv sync --extra langfuse`.
2. In the client config, change `run garmin-watch-mcp` to
   `run --extra langfuse garmin-watch-mcp`.
3. Add `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to the server's `env`, plus
   `LANGFUSE_BASE_URL` if you don't use Langfuse Cloud.

By default, traces hold only tool names, timings and error class names.
`LANGFUSE_CAPTURE_DATA=true` also sends your health data; only turn it on with a Langfuse
instance you trust, such as a self-hosted one.

## Troubleshooting

| Message | What to do |
|---|---|
| `Missing required environment variable(s): …` | No saved tokens were found. Run `garmin-watch-mcp login`, or pass `GARMIN_EMAIL`/`GARMIN_PASSWORD`. If you set `GARMINTOKENS`, check the client passes the same value. |
| `This Garmin account uses MFA…` | Run `garmin-watch-mcp login` in a terminal, then restart the client. |
| `Garmin Connect login failed…` | Tokens expired or the password is wrong. Run `garmin-watch-mcp login` again. |
| `Rate limited by Garmin Connect…` | Garmin throttles logins aggressively. Wait 15–60 minutes; use saved tokens so the server doesn't log in with a password. |
| `Garmin Connect API error 4xx/5xx` | Garmin may have changed an endpoint. Update (`git pull && uv sync`) and open an issue if it persists. |
| A tool returns `no_data: true` | The watch hasn't recorded or synced that metric for that day (not every watch supports HRV or training readiness). |
| Tools don't appear in Claude Desktop | Use the absolute path to `uv`, check the JSON is valid, and fully quit and reopen Claude Desktop. Logs are in `~/Library/Logs/Claude/` (macOS) or `%APPDATA%\Claude\logs\` (Windows). |

## Updating

```bash
cd /path/to/garmin-watch-mcp
git pull
uv sync
```

Then restart your MCP client.

## Uninstalling

1. Remove the `garmin` entry from `claude_desktop_config.json`, or run
   `claude mcp remove garmin`.
2. Delete the `garmin-watch-mcp` folder and the `~/.garminconnect` token folder.

## A note on your tokens

The saved tokens grant access to your Garmin account without a password. Keep
`~/.garminconnect` and any `GARMINTOKENS` value private. To revoke them, delete the folder
and change your Garmin password.
