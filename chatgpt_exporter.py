#!/usr/bin/env python3
"""
ChatGPT Team Workspace Bulk Exporter
=====================================
Exports all conversations to Markdown files organised by Project folder.

SETUP:
1. Install dependencies:
       pip install requests

2. Get your session token:
   - Open ChatGPT in Chrome and log in to your Team workspace
   - Open DevTools (F12) → Application → Cookies → https://chatgpt.com
   - Copy the value of the cookie named: __Secure-next-auth.session-token
   - Paste it below as SESSION_TOKEN

3. Get your workspace ID (for Team plan):
   - Look at the URL when inside your Team workspace, e.g.:
     https://chatgpt.com/g/g-xxx.../project  ← not this
     https://chatgpt.com/?workspace=abc123   ← the workspace param
   - OR open DevTools → Network → look for requests to backend-api
     that include a workspace_id header or param
   - You can also leave WORKSPACE_ID as None to try without it first

4. Run:
       python3 chatgpt_exporter.py
"""

import os
import re
import json
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURATION — fill these in
# ─────────────────────────────────────────────

# If ChatGPT split the token into two cookies (.0 and .1), paste each part below.
# If there is only one cookie named __Secure-next-auth.session-token, put it in SESSION_TOKEN_0 and leave SESSION_TOKEN_1 empty.
SESSION_TOKEN_0 = ""
SESSION_TOKEN_1 = ""  # Leave as "" if there is no .1 cookie

def _build_session_cookie() -> str:
    if SESSION_TOKEN_1 and SESSION_TOKEN_1 != "PASTE_TOKEN_1_HERE":
        return (
            f"__Secure-next-auth.session-token.0={SESSION_TOKEN_0}; "
            f"__Secure-next-auth.session-token.1={SESSION_TOKEN_1}"
        )
    return f"__Secure-next-auth.session-token={SESSION_TOKEN_0}"

# Optional: your Team workspace ID (leave as None to try without)
WORKSPACE_ID = "[put your workspace ID here]"

# Projects — extracted from your ChatGPT project URLs
# Format: (gizmo_id, folder_name)
PROJECTS = [
    ("[Project ID]", "[Add your projects here]") #e.g  ("g-xxx...", "Bali Holday Planning")
]

# Where to save exported files
OUTPUT_DIR = "./chatgpt_export"

# How many conversations to fetch per API page (max 100)
PAGE_SIZE = 100

# Delay between API requests in seconds (be polite to the API)
REQUEST_DELAY = 0.5

# ─────────────────────────────────────────────


BASE_URL = "https://chatgpt.com/backend-api"


def parse_timestamp(ts, fmt="%Y-%m-%d %H:%M") -> str:
    """Parse a timestamp that may be a Unix number or an ISO 8601 string."""
    if not ts:
        return "Unknown"
    try:
        return datetime.fromtimestamp(float(ts)).strftime(fmt)
    except (ValueError, TypeError):
        pass
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.astimezone().strftime(fmt)
    except ValueError:
        return str(ts)


def get_headers():
    headers = {
        "Cookie": _build_session_cookie(),
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://chatgpt.com/",
    }
    if WORKSPACE_ID:
        headers["ChatGPT-Account-ID"] = WORKSPACE_ID
    return headers


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = name.strip('. ')
    return name[:100] or "Untitled"


def get_access_token():
    """Exchange session token for a bearer access token."""
    print("🔑 Getting access token...")
    headers = {
        "Cookie": _build_session_cookie(),
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://chatgpt.com/",
        "Origin": "https://chatgpt.com",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    resp = requests.get(
        "https://chatgpt.com/api/auth/session",
        headers=headers,
    )
    print(f"  Session endpoint status: {resp.status_code}")
    print(f"  Response body (first 300 chars): {repr(resp.text[:300])}")
    if resp.status_code != 200:
        raise Exception(f"Failed to get session: {resp.status_code} {resp.text[:200]}")
    if not resp.text.strip():
        raise Exception("Empty response from session endpoint — session token may be expired. Please get a fresh token from your browser.")
    data = resp.json()
    token = data.get("accessToken")
    if not token:
        print(f"  Full session response keys: {list(data.keys())}")
        raise Exception("No accessToken in session response. Check your SESSION_TOKEN.")
    print("✅ Access token obtained")
    return token


def fetch_conversations_page(access_token: str, gizmo_id: str = None, folder_name: str = None) -> list:
    """Fetch all conversations (optionally scoped to a project) across all pages."""
    headers = get_headers()
    headers["Authorization"] = f"Bearer {access_token}"

    all_convos = []

    if gizmo_id:
        # Projects use cursor-based pagination at a gizmo-specific endpoint
        url = f"{BASE_URL}/gizmos/{gizmo_id}/conversations"
        cursor = None
        while True:
            params = {}
            if cursor:
                params["cursor"] = cursor
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                print(f"  ⚠️  Error fetching project conversations: {resp.status_code} {resp.text[:100]}")
                break
            data = resp.json()
            items = data.get("items", data.get("conversations", []))
            if folder_name:
                for item in items:
                    item["_folder_name"] = folder_name
            all_convos.extend(items)
            cursor = data.get("cursor")
            if not cursor or not items:
                break
            time.sleep(REQUEST_DELAY)
    else:
        # Regular conversations use offset-based pagination
        offset = 0
        while True:
            params = {"offset": offset, "limit": PAGE_SIZE, "order": "updated"}
            resp = requests.get(f"{BASE_URL}/conversations", headers=headers, params=params)
            if resp.status_code != 200:
                print(f"  ⚠️  Error fetching page at offset {offset}: {resp.status_code}")
                break
            data = resp.json()
            items = data.get("items", [])
            total = data.get("total", 0)
            all_convos.extend(items)
            if len(all_convos) >= total or not items:
                break
            offset += PAGE_SIZE
            time.sleep(REQUEST_DELAY)

    return all_convos


def fetch_all_conversations(access_token: str) -> list:
    """Fetch unorganised conversations then each project's conversations."""
    print("📋 Fetching unorganised conversations...")
    all_convos = fetch_conversations_page(access_token)
    print(f"  Found {len(all_convos)} unorganised conversations")

    print(f"\n📁 Fetching {len(PROJECTS)} projects...")
    for gizmo_id, folder_name in PROJECTS:
        print(f"  Project: {folder_name}...")
        project_convos = fetch_conversations_page(access_token, gizmo_id=gizmo_id, folder_name=folder_name)
        print(f"    Found {len(project_convos)} conversations")
        all_convos.extend(project_convos)
        time.sleep(REQUEST_DELAY)

    print(f"\n✅ Found {len(all_convos)} conversations total")
    return all_convos


def fetch_conversation_detail(convo_id: str, access_token: str) -> dict:
    """Fetch the full message content of a single conversation."""
    headers = get_headers()
    headers["Authorization"] = f"Bearer {access_token}"

    resp = requests.get(
        f"{BASE_URL}/conversation/{convo_id}",
        headers=headers,
    )
    if resp.status_code != 200:
        print(f"    ⚠️  Could not fetch conversation {convo_id}: {resp.status_code}")
        return {}
    return resp.json()


def extract_messages(detail: dict) -> list:
    """
    Walk the conversation tree and return messages in order.
    Returns list of {"role": str, "content": str, "timestamp": str}
    """
    mapping = detail.get("mapping", {})
    if not mapping:
        return []

    # Find the root node
    root_id = None
    for node_id, node in mapping.items():
        if node.get("parent") is None:
            root_id = node_id
            break

    if not root_id:
        return []

    messages = []

    def walk(node_id):
        node = mapping.get(node_id)
        if not node:
            return

        msg = node.get("message")
        if msg:
            role = msg.get("author", {}).get("role", "unknown")
            content_obj = msg.get("content", {})
            content_type = content_obj.get("content_type", "")
            parts = content_obj.get("parts", [])

            # Only include user and assistant messages with real content
            if role in ("user", "assistant") and parts:
                text_parts = []
                for part in parts:
                    if isinstance(part, str) and part.strip():
                        text_parts.append(part)
                    elif isinstance(part, dict):
                        # Handle code/other structured content
                        if part.get("content_type") == "code":
                            code = part.get("text", "")
                            if code:
                                text_parts.append(f"```\n{code}\n```")

                if text_parts:
                    ts = msg.get("create_time")
                    timestamp = ""
                    if ts:
                        timestamp = parse_timestamp(ts)

                    messages.append({
                        "role": role,
                        "content": "\n\n".join(text_parts),
                        "timestamp": timestamp,
                    })

        # Walk children (take first child for linear conversations)
        children = node.get("children", [])
        for child_id in children:
            walk(child_id)
            break  # Follow only the main branch (not all regenerations)

    walk(root_id)
    return messages


def conversation_to_markdown(convo_meta: dict, messages: list) -> str:
    """Convert a conversation to a Markdown string."""
    title = convo_meta.get("title", "Untitled")
    created = convo_meta.get("create_time")
    updated = convo_meta.get("update_time")

    created_str = parse_timestamp(created)
    updated_str = parse_timestamp(updated)

    lines = [
        f"# {title}",
        f"",
        f"**Created:** {created_str}  ",
        f"**Last updated:** {updated_str}",
        f"",
        f"---",
        f"",
    ]

    for msg in messages:
        role_label = "🧑 **You**" if msg["role"] == "user" else "🤖 **ChatGPT**"
        ts = f" _{msg['timestamp']}_" if msg["timestamp"] else ""
        lines.append(f"{role_label}{ts}")
        lines.append("")
        lines.append(msg["content"])
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def get_project_name(convo_meta: dict, access_token: str, project_cache: dict) -> str:
    """Resolve the project name for a conversation."""
    project_id = (
        convo_meta.get("_project_id")
        or convo_meta.get("project_id")
        or convo_meta.get("workspace_id")
        or convo_meta.get("gizmo_id")
    )

    if not project_id:
        return "_Uncategorized"

    if project_id in project_cache:
        return project_cache[project_id]

    headers = get_headers()
    headers["Authorization"] = f"Bearer {access_token}"

    # Try the projects endpoint first
    try:
        resp = requests.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("name") or data.get("title") or project_id
            project_cache[project_id] = sanitize_filename(name)
            return project_cache[project_id]
    except Exception:
        pass

    # Fall back to gizmos endpoint
    try:
        resp = requests.get(f"{BASE_URL}/gizmos/{project_id}", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("gizmo", {}).get("display", {}).get("name", project_id)
            project_cache[project_id] = sanitize_filename(name)
            return project_cache[project_id]
    except Exception:
        pass

    project_cache[project_id] = sanitize_filename(project_id)
    return project_cache[project_id]


def main():
    print("=" * 50)
    print("  ChatGPT Team Workspace Exporter")
    print("=" * 50)
    print()

    if SESSION_TOKEN_0 == "PASTE_TOKEN_0_HERE":
        print("❌ Please set your SESSION_TOKEN_0 in the script first!")
        return

    # Get access token
    access_token = get_access_token()

    # Fetch all conversation metadata
    all_convos = fetch_all_conversations(access_token)

    if not all_convos:
        print("❌ No conversations found. Check your token and workspace ID.")
        return

    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    project_cache = {}
    title_counts = {}  # Track duplicates per folder
    success = 0
    errors = 0

    print(f"\n📁 Exporting to: {output_path.resolve()}")
    print(f"⏳ Processing {len(all_convos)} conversations...\n")

    for i, convo in enumerate(all_convos, 1):
        convo_id = convo.get("id", "")
        title = convo.get("title") or "Untitled"
        safe_title = sanitize_filename(title)

        print(f"  [{i}/{len(all_convos)}] {title[:60]}...")

        # Determine project folder
        # The conversations list endpoint includes a 'workspace_id' or similar
        # Try several possible field names
        project_folder = "_Uncategorized"

        # Use pre-tagged folder name if available, otherwise fall back to API lookup
        if convo.get("_folder_name"):
            project_folder = convo["_folder_name"]
        else:
            for field in ("project_id", "workspace_id", "conversation_template_id"):
                val = convo.get(field)
                if val:
                    project_folder = get_project_name(convo, access_token, project_cache)
                    break

        # Create folder
        folder = output_path / project_folder
        folder.mkdir(parents=True, exist_ok=True)

        # Handle duplicate titles within same folder
        folder_key = f"{project_folder}/{safe_title}"
        if folder_key in title_counts:
            title_counts[folder_key] += 1
            updated = convo.get("update_time")
            date_str = parse_timestamp(updated, fmt="%Y%m%d") if updated else str(title_counts[folder_key])
            filename = f"{safe_title}_{date_str}.md"
        else:
            title_counts[folder_key] = 1
            filename = f"{safe_title}.md"

        filepath = folder / filename

        # Skip if already downloaded
        if filepath.exists():
            print(f"  [{i}/{len(all_convos)}] ⏭️  Skipping (already exists): {title[:60]}")
            success += 1
            continue

        # Fetch full conversation
        detail = fetch_conversation_detail(convo_id, access_token)
        time.sleep(REQUEST_DELAY)

        if not detail:
            errors += 1
            continue

        # Extract messages and convert to markdown
        messages = extract_messages(detail)
        markdown = conversation_to_markdown(convo, messages)

        # Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)

        success += 1

    print(f"\n{'=' * 50}")
    print(f"✅ Export complete!")
    print(f"   Saved:  {success} conversations")
    print(f"   Errors: {errors} conversations")
    print(f"   Output: {output_path.resolve()}")
    print(f"{'=' * 50}")

    # Print folder summary
    print("\n📂 Folder summary:")
    folders = {}
    for p in output_path.rglob("*.md"):
        folder_name = p.parent.name
        folders[folder_name] = folders.get(folder_name, 0) + 1
    for folder_name, count in sorted(folders.items()):
        print(f"   {folder_name}/  ({count} files)")


if __name__ == "__main__":
    main()
