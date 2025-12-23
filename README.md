# anon-slack

A Python script to delete all of your own messages from Slack workspaces.

## Features

- Deletes messages from public channels, private channels, group DMs, and direct messages
- Only deletes YOUR messages (not others')
- Handles Slack API rate limiting automatically

## Requirements

- Python 3.8+
- Slack User OAuth Token with scopes: `chat:write`, `channels:history`, `channels:read`, `groups:history`, `groups:read`, `im:history`, `im:read`, `mpim:history`, `mpim:read`, `users:read`

## Setup

### 1. Create a virtual environment

```bash
python3 -m venv venv
```

### 2. Activate the virtual environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install requests
```

### 4. Configure your Slack token

Edit `anon-slack.py` and replace the `TOKEN` variable with your User OAuth Token (starts with `xoxp-`).

## Usage

```bash
python3 anon-slack.py
```

## Resume Support

The script creates a `processed_conversations.json` file to track which conversations have been fully processed. If the script is interrupted (Ctrl+C, network issue, etc.), you can simply run it again and it will skip already-processed conversations.

**To start over from scratch**, delete the cache file:

```bash
rm processed_conversations.json
```
