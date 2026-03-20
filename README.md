# ChatGPT Conversation Exporter

Bulk-export your ChatGPT conversations to clean Markdown files, organised by Project folder. Works with **Free**, **Plus**, **Pro**, **Team**, and **Enterprise** plans.

## Disclaimer

> **This tool uses unofficial, undocumented ChatGPT internal APIs and may violate [OpenAI's Terms of Use](https://openai.com/policies/terms-of-use).** In particular, the Terms prohibit *"automatically or programmatically extract[ing] data or Output"* and *"reverse engineer[ing] … the source code or underlying components"* of their services. Using this tool could result in account suspension or termination.
>
> **Use at your own risk.** The authors are not responsible for any consequences arising from its use.
>
> If you want a ToS-compliant way to export your data, OpenAI offers a built-in export: go to **Settings > Data Controls > Export data** in ChatGPT. This sends a zip file of all your conversations in JSON format to your email.

## Features

- Exports all conversations from your ChatGPT account
- Organises output into folders matching your ChatGPT Projects
- Produces readable Markdown with timestamps and role labels
- Supports incremental export — already-downloaded conversations are skipped on re-run
- Handles duplicate conversation titles gracefully
- Configurable rate limiting to stay friendly to the API

## Prerequisites

- **Python 3.8+**
- A ChatGPT account with at least one conversation

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/richlow/chatGPT_extractor.git
cd chatGPT_extractor
```

### 2. Install dependencies

```bash
pip install requests
```

### 3. Get your session token

1. Open [chatgpt.com](https://chatgpt.com) in Chrome (or any Chromium-based browser) and log in.
2. Open DevTools — press **F12** (or **Cmd+Option+I** on macOS).
3. Go to **Application** → **Cookies** → `https://chatgpt.com`.
4. Find the cookie named `__Secure-next-auth.session-token` and copy its value.

> **Note:** Some accounts split this cookie into two parts:
> `__Secure-next-auth.session-token.0` and `__Secure-next-auth.session-token.1`.
> If you see both, copy each one separately.

### 4. Configure the script

Open `chatgpt_exporter.py` and fill in the configuration section near the top:

```python
# Single cookie — paste the full value here
SESSION_TOKEN_0 = "your-session-token-here"
SESSION_TOKEN_1 = ""  # Leave empty if you only have one cookie

# For split cookies, paste each part
SESSION_TOKEN_0 = "first-part-here"
SESSION_TOKEN_1 = "second-part-here"
```

### 5. (Optional) Set your Workspace ID

If you're on a **Team** or **Enterprise** plan, set the workspace ID so the exporter can access your team conversations:

```python
WORKSPACE_ID = "your-workspace-id"
```

You can find this in your browser's URL bar (`?workspace=abc123`) or in DevTools under **Network** requests to `backend-api`.

If you're on a personal plan, set this to `None`:

```python
WORKSPACE_ID = None
```

### 6. (Optional) Add your Projects

If you use ChatGPT Projects and want conversations grouped by project folder, add them to the `PROJECTS` list. Each entry needs the **gizmo ID** (from the project URL) and a human-readable folder name:

```python
PROJECTS = [
    ("g-abc123...", "Work Research"),
    ("g-def456...", "Holiday Planning"),
]
```

To find a project's gizmo ID, open the project in ChatGPT and look at the URL — it will contain something like `g-p-xxxxxxx`.

Leave the list empty to export only unorganised conversations:

```python
PROJECTS = []
```

### 7. Run the exporter

```bash
python3 chatgpt_exporter.py
```

Exported Markdown files will be saved to `./chatgpt_export/` by default (configurable via `OUTPUT_DIR`).

## Output Structure

```
chatgpt_export/
├── _Uncategorized/
│   ├── How to make sourdough.md
│   └── Python debugging help.md
├── Work Research/
│   ├── Quarterly report analysis.md
│   └── Competitor overview.md
└── Holiday Planning/
    └── Bali itinerary.md
```

Each Markdown file includes:

- Conversation title as a heading
- Creation and last-updated timestamps
- Messages labelled by role (You / ChatGPT) with timestamps

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `SESSION_TOKEN_0` | `""` | Primary session cookie value (required) |
| `SESSION_TOKEN_1` | `""` | Second part of a split session cookie (if applicable) |
| `WORKSPACE_ID` | `None` | Team/Enterprise workspace ID (optional) |
| `PROJECTS` | `[]` | List of `(gizmo_id, folder_name)` tuples |
| `OUTPUT_DIR` | `"./chatgpt_export"` | Directory for exported files |
| `PAGE_SIZE` | `100` | Conversations per API page (max 100) |
| `REQUEST_DELAY` | `0.5` | Seconds between API requests |

## Troubleshooting

**"Empty response from session endpoint"**
Your session token has expired. Go back to your browser, refresh ChatGPT, and copy a fresh token from DevTools.

**"No accessToken in session response"**
Double-check that you copied the full cookie value. If the token is split across `.0` and `.1` cookies, make sure both are filled in.

**"No conversations found"**
Verify your `WORKSPACE_ID` is correct (Team/Enterprise), or set it to `None` for personal accounts.

**403 or 401 errors**
Session tokens expire periodically. Grab a fresh one from your browser and try again.

## License

This project is licensed under the [MIT License](LICENSE).
