import requests
import time
import json
import os

CACHE_FILE = "processed_conversations.json"
INITIAL_RETRY_DELAY = 2  # Start with 2 seconds
MAX_RETRY_DELAY = 300    # Cap at 5 minutes

# Global retry delay that persists across calls
current_retry_delay = INITIAL_RETRY_DELAY

# Your Slack user OAuth token
# Scopes needed: chat:write, channels:history, channels:read, groups:history,
#                groups:read, im:history, im:read, mpim:history, mpim:read, users:read
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        print("Create it with: cp config.example.json config.json")
        print("Then add your Slack token to the file.")
        exit(1)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

config = load_config()
TOKEN = config.get("slack_token")

if not TOKEN:
    print(f"Error: 'slack_token' not found in {CONFIG_FILE}")
    exit(1)

headers = {"Authorization": f"Bearer {TOKEN}"}

def load_cache():
    """Load the set of processed conversation IDs from cache file."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_cache(processed_ids):
    """Save the set of processed conversation IDs to cache file."""
    with open(CACHE_FILE, "w") as f:
        json.dump(list(processed_ids), f)

def slack_api_call(method, url, **kwargs):
    """Make a Slack API call with retry logic for rate limiting."""
    global current_retry_delay

    while True:
        if method == "get":
            response = requests.get(url, **kwargs)
        else:
            response = requests.post(url, **kwargs)

        result = response.json()


        if result.get("error") == "ratelimited":
            current_retry_delay = min(current_retry_delay * 2, MAX_RETRY_DELAY)
            print(f"  Rate limited. Waiting {current_retry_delay}s before retry...")
            time.sleep(current_retry_delay)
            continue
        else:
            if current_retry_delay >= 2:
                current_retry_delay = current_retry_delay // 2
            return result

        return result

def get_my_user_id():
    """Get the authenticated user's ID."""
    result = slack_api_call("get", "https://slack.com/api/auth.test", headers=headers)
    if result.get("ok"):
        return result.get("user_id")
    return None

def get_all_conversations(cursor=None):
    """Fetch all conversations the user is a member of."""
    params = {
        "types": "public_channel,private_channel,mpim,im",
        "limit": 200,
    }
    if cursor:
        params["cursor"] = cursor

    return slack_api_call("get", "https://slack.com/api/conversations.list", headers=headers, params=params)

def get_messages(channel_id, cursor=None):
    """Fetch messages from a conversation."""
    params = {
        "channel": channel_id,
        "limit": 200,
    }
    if cursor:
        params["cursor"] = cursor

    return slack_api_call("get", "https://slack.com/api/conversations.history", headers=headers, params=params)

def delete_message(channel_id, ts):
    """Delete a single message by timestamp."""
    return slack_api_call("post", "https://slack.com/api/chat.delete", headers=headers, json={"channel": channel_id, "ts": ts})

def get_channel_name(channel):
    """Get a readable name for a channel."""
    if channel.get("is_im"):
        return f"DM:{channel.get('user', 'unknown')}"
    return channel.get("name", channel.get("id"))

def delete_messages_in_channel(channel_id, channel_name, my_user_id):
    """Delete all of the user's messages in a single channel."""
    deleted = 0
    skipped = 0
    cursor = None

    while True:
        result = get_messages(channel_id, cursor)

        if not result.get("ok"):
            error = result.get("error")
            if error == "channel_not_found":
                print(f"  Skipping {channel_name}: channel not accessible")
            else:
                print(f"  Error in {channel_name}: {error}")
            break

        messages = result.get("messages", [])
        if not messages:
            break

        for msg in messages:
            ts = msg.get("ts")
            msg_user = msg.get("user")

            # Only delete YOUR messages
            if msg_user != my_user_id:
                skipped += 1
                continue

            # Skip system messages
            if msg.get("subtype"):
                skipped += 1
                continue

            delete_result = delete_message(channel_id, ts)

            if delete_result.get("ok"):
                deleted += 1
                print(f"  Deleted: {msg.get('text', '')[:50]}...")
            else:
                error = delete_result.get("error")
                if error == "cant_delete_message":
                    skipped += 1
                else:
                    print(f"  Failed to delete: {error}")

        # Check for more pages
        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
        print(f"  Fetching more messages from {channel_name}...")

    return deleted, skipped

def main():
    # Get your user ID
    my_user_id = get_my_user_id()
    if not my_user_id:
        print("Error: Could not get your user ID. Check your token.")
        return

    print(f"Your user ID: {my_user_id}")

    # Get all conversations
    all_channels = []
    cursor = None

    print("Fetching all conversations...")
    while True:
        result = get_all_conversations(cursor)

        if not result.get("ok"):
            print(f"Error fetching conversations: {result.get('error')}")
            return

        channels = result.get("channels", [])
        all_channels.extend(channels)

        cursor = result.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    print(f"Found {len(all_channels)} conversations")

    # Load cache and filter out already-processed conversations
    processed_ids = load_cache()
    channels_to_process = [c for c in all_channels if c.get("id") not in processed_ids]

    print(f"Already processed: {len(processed_ids)}, Remaining: {len(channels_to_process)}\n")

    total_deleted = 0
    total_skipped = 0

    for i, channel in enumerate(channels_to_process):
        channel_id = channel.get("id")
        channel_name = get_channel_name(channel)
        remaining = len(channels_to_process) - i - 1

        print(f"Processing: {channel_name} ({channel_id})")
        deleted, skipped = delete_messages_in_channel(channel_id, channel_name, my_user_id)
        total_deleted += deleted
        total_skipped += skipped

        if deleted > 0:
            print(f"  -> Deleted {deleted} messages")

        # If no messages were deleted, this conversation is done - add to cache
        if deleted == 0:
            processed_ids.add(channel_id)
            save_cache(processed_ids)

        print(f"  -> {remaining} conversations remaining\n")

    print(f"Done! Deleted: {total_deleted}, Skipped: {total_skipped}")

if __name__ == "__main__":
    main()
