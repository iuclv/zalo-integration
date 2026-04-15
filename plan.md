# Zalo OA Auto-Reply Integration Plan

## Goal

Build a minimal server that connects to a Zalo Official Account (OA). When a user opens the OA on Zalo and sends any message, the server automatically replies with a "Hello" message.

---

## How It Works

```
User sends message on Zalo
        │
        ▼
Zalo servers receive message
        │
        ▼
Zalo POSTs webhook event to your server
(event: "user_send_text", contains sender user_id + message text)
        │
        ▼
Your server calls Zalo OA Reply API
POST https://openapi.zalo.me/v3.0/oa/message/cs
(sends "Hello!" back to the user)
        │
        ▼
User sees "Hello!" reply in Zalo chat
```

---

## Prerequisites (Manual Setup on Zalo)

Before writing any code, you need these accounts/configs:

1. **Zalo Developer Account** — register at https://developers.zalo.me
2. **Create a Zalo App** — go to https://developers.zalo.me/apps, click "Thêm ứng dụng mới", fill in name/category/description (20-500 chars each), then activate the app
3. **Create/Link a Zalo Official Account** — create at https://oa.zalo.me if you don't have one, then link it to your app
4. **Request API permissions** — in your app settings, go to API Registration and request the "send message" permission, submit for review
5. **Get initial Access Token** — use the API Explorer at https://developers.zalo.me/tools/explorer to generate your first OA Access Token + Refresh Token
6. **Configure Webhook** — in your app's Webhook settings, register your server's public URL (e.g. `https://your-domain.com/webhook`). Subscribe to the "user_send_text" event

---

## Tech Stack

| Component        | Choice                  | Why                                                      |
| ---------------- | ----------------------- | -------------------------------------------------------- |
| Language         | **Python 3.10+**        | Simple, readable, quick to prototype                     |
| Framework        | **Flask**               | Minimal HTTP framework, perfect for a single-endpoint server |
| HTTP Client      | **requests**            | Clean API for calling Zalo's REST endpoints              |
| Environment Vars | **python-dotenv**       | Store secrets (app_id, secret_key, tokens) outside code  |
| Tunnel (dev)     | **ngrok**               | Expose localhost to the internet so Zalo can reach your webhook |

### Why Python + Flask?

- The entire app is ~50 lines of code
- No database needed (tokens stored in env/memory for this minimal version)
- Flask handles the webhook POST endpoint trivially
- Fast startup, low memory footprint

---

## Project Structure

```
zalo-integration/
├── plan.md
├── requirements.txt
├── .env              # secrets — never commit this
├── .env.example      # template for .env
└── src/
    └── app.py        # the entire app
```

---

## Key API Details

### Webhook Event (incoming — Zalo → Your Server)

When a user sends a text message to your OA, Zalo sends a POST to your webhook URL:

```json
{
  "event_name": "user_send_text",
  "sender": {
    "id": "<user_id>"
  },
  "message": {
    "text": "Hi there"
  },
  "timestamp": "1750316131602"
}
```

### Reply API (outgoing — Your Server → Zalo)

**Endpoint:** `POST https://openapi.zalo.me/v3.0/oa/message/cs`

**Headers:**
```
Content-Type: application/json
access_token: <YOUR_OA_ACCESS_TOKEN>
```

**Body:**
```json
{
  "recipient": {
    "user_id": "<user_id_from_webhook>"
  },
  "message": {
    "text": "Hello!"
  }
}
```

### Token Refresh

Access tokens expire after **1 hour**. Use the refresh token to get a new one:

**Endpoint:** `POST https://oauth.zaloapp.com/v4/oa/access_token`

**Headers:**
```
Content-Type: application/x-www-form-urlencoded
secret_key: <YOUR_APP_SECRET_KEY>
```

**Body (form-urlencoded):**
```
app_id=<YOUR_APP_ID>&grant_type=refresh_token&refresh_token=<YOUR_REFRESH_TOKEN>
```

The response returns a new `access_token` (1h) and a new `refresh_token` (3 months, single-use).

---

## Implementation Steps

### Step 1: Initialize project
```bash
python -m venv venv
source venv/bin/activate
pip install flask requests python-dotenv
pip freeze > requirements.txt
```

### Step 2: Create `.env` with credentials
```
APP_ID=your_app_id
APP_SECRET=your_app_secret_key
OA_ACCESS_TOKEN=your_initial_access_token
OA_REFRESH_TOKEN=your_initial_refresh_token
PORT=3000
```

### Step 3: Implement `src/app.py`

The server needs to:
1. Listen for POST requests on `/webhook`
2. On `user_send_text` events, extract the sender's `user_id`
3. Call the Zalo Reply API to send "Hello!" back
4. Auto-refresh the access token before it expires (every ~55 minutes)

### Step 4: Run locally with ngrok
```bash
python src/app.py        # start the server on port 3000
ngrok http 3000          # expose it publicly
```

Then copy the ngrok HTTPS URL into your Zalo App's webhook settings.

### Step 5: Test
- Open Zalo on your phone
- Find your Official Account
- Send any message
- You should receive "Hello!" back instantly

---

## Constraints & Notes

- **48-hour reply window**: Zalo OAs can only reply to a user within 48 hours of their last message. After that, you need "proactive push" quota (not relevant for auto-reply).
- **Rate limit**: ~10 requests/second on the message API.
- **Token refresh is critical**: Access tokens only last 1 hour. The app must auto-refresh or it will stop working.
- **Webhook must be HTTPS**: Zalo requires an HTTPS endpoint. Use ngrok for local dev, or deploy behind a reverse proxy with TLS for production.
- **OA verification**: Some API features require your OA to be verified (business registration). Basic messaging should work without it for testing.
