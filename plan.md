# Zalo OA Auto-Reply Integration Plan

## Goal

Build a minimal server that connects to a Zalo Official Account (OA). When a user opens the OA on Zalo and sends any message (text, image, file, or audio), the server automatically replies with a "Hello" message and can process/store media attachments.

---

## How It Works

```
User sends message on Zalo (text, image, file, audio, video)
        │
        ▼
Zalo servers receive message
        │
        ▼
Zalo POSTs webhook event to your server
(event: "user_send_text" / "user_send_image" / "user_send_file" / "user_send_audio")
        │
        ▼
Your server processes the event:
  - Text → extract message text
  - Image → download from message.photo_url
  - File → download from message.url
  - Audio → download from message.url
        │
        ▼
Your server calls Zalo OA Reply API
POST https://openapi.zalo.me/v3.0/oa/message/cs
(sends "Hello!" back to the user, optionally with media attachments)
        │
        ▼
User sees reply in Zalo chat
```

---

## Prerequisites (Manual Setup on Zalo)

Before writing any code, you need these accounts/configs:

1. **Zalo Developer Account** — register at https://developers.zalo.me
2. **Create a Zalo App** — go to https://developers.zalo.me/apps, click "Thêm ứng dụng mới", fill in name/category/description (20-500 chars each), then activate the app
3. **Create/Link a Zalo Official Account** — create at https://oa.zalo.me if you don't have one, then link it to your app
4. **Request API permissions** — in your app settings, go to API Registration and request the "send message" permission, submit for review
5. **Get initial Access Token** — use the API Explorer at https://developers.zalo.me/tools/explorer to generate your first OA Access Token + Refresh Token
6. **Configure Webhook** — in your app's Webhook settings, register your server's public URL (e.g. `https://your-domain.com/webhook`). Subscribe to these events: `user_send_text`, `user_send_image`, `user_send_file`, `user_send_audio`

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

### Webhook Events (incoming — Zalo → Your Server)

When a user sends a message to your OA, Zalo POSTs to your webhook URL. The payload varies by event type:

#### `user_send_text`
```json
{
  "event_name": "user_send_text",
  "sender": { "id": "<user_id>" },
  "message": { "text": "Hi there", "msg_id": "<msg_id>" },
  "timestamp": "1750316131602"
}
```

#### `user_send_image`
**Important:** The image URL field is `photo_url`, NOT `photo`.
```json
{
  "event_name": "user_send_image",
  "sender": { "id": "<user_id>" },
  "message": { "photo_url": "https://...", "msg_id": "<msg_id>" },
  "timestamp": "..."
}
```

#### `user_send_file`
```json
{
  "event_name": "user_send_file",
  "sender": { "id": "<user_id>" },
  "message": { "url": "https://...", "msg_id": "<msg_id>" },
  "timestamp": "..."
}
```

#### `user_send_audio`
```json
{
  "event_name": "user_send_audio",
  "sender": { "id": "<user_id>" },
  "message": { "url": "https://...", "msg_id": "<msg_id>" },
  "timestamp": "..."
}
```

#### Webhook Security

Zalo signs webhook requests with HMAC SHA256 using your OA Secret Key. Verify the `mac` field in the payload to ensure the request is authentic.

### Upload APIs (Your Server → Zalo)

Before sending media messages back to users, you must upload the media to Zalo first. All upload endpoints use `multipart/form-data` with the `access_token` in the header.

| Media Type | Endpoint                                            |
| ---------- | --------------------------------------------------- |
| Image      | `POST https://openapi.zalo.me/v3.0/oa/upload/image` |
| GIF        | `POST https://openapi.zalo.me/v3.0/oa/upload/gif`   |
| File       | `POST https://openapi.zalo.me/v3.0/oa/upload/file`  |

**Headers:**
```
access_token: <YOUR_OA_ACCESS_TOKEN>
```

**Body:** `multipart/form-data` with a `file` field containing the binary data.

**Response:** Returns an `attachment_id` (images/GIFs) or `token` (files) for use in messages.

**Python example — upload image:**
```python
def upload_image(access_token: str, file_path: str) -> str:
    with open(file_path, "rb") as f:
        resp = requests.post(
            "https://openapi.zalo.me/v3.0/oa/upload/image",
            headers={"access_token": access_token},
            files={"file": f},
            timeout=30,
        )
    data = resp.json()
    return data["data"]["attachment_id"]
```

Same pattern applies for `/upload/file` and `/upload/gif`. Audio does not have a dedicated upload endpoint — use `/upload/file` instead.

### Reply API (outgoing — Your Server → Zalo)

**Endpoint:** `POST https://openapi.zalo.me/v3.0/oa/message/cs`

**Headers:**
```
Content-Type: application/json
access_token: <YOUR_OA_ACCESS_TOKEN>
```

#### Send text reply:
```json
{
  "recipient": { "user_id": "<user_id>" },
  "message": { "text": "Hello!" }
}
```

#### Send image reply (by attachment_id from upload):
```json
{
  "recipient": { "user_id": "<user_id>" },
  "message": {
    "attachment": {
      "type": "template",
      "payload": {
        "template_type": "media",
        "elements": [{ "media_type": "image", "attachment_id": "<id>" }]
      }
    }
  }
}
```

#### Send image reply (by URL — must be https):
```json
{
  "recipient": { "user_id": "<user_id>" },
  "message": {
    "attachment": {
      "type": "template",
      "payload": {
        "template_type": "media",
        "elements": [{ "media_type": "image", "url": "https://..." }]
      }
    }
  }
}
```

#### Send file reply (by token from upload):
```json
{
  "recipient": { "user_id": "<user_id>" },
  "message": {
    "attachment": {
      "type": "file",
      "payload": { "token": "<file_token>" }
    }
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
2. Handle multiple event types:
   - `user_send_text` → extract `message.text`
   - `user_send_image` → extract `message.photo_url`, download the image
   - `user_send_file` → extract `message.url`, download the file
   - `user_send_audio` → extract `message.url`, download the audio
3. Call the Zalo Reply API to send "Hello!" back (optionally with media)
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
- **Media URLs from webhooks may expire**: Zalo hosts user-sent media on its CDN. Download files promptly if you need to persist them.
- **Outbound images must be https:// URLs**: Local file paths are rejected. If you generate images locally, upload them via the upload API first.
- **No dedicated audio upload endpoint**: Use `/v3.0/oa/upload/file` for audio files.
- **`photo_url` not `photo`**: Inbound image webhooks use `message.photo_url` for the image URL. Using `message.photo` will fail silently (it's undefined).
- **Webhook MAC verification**: Validate the `mac` field using HMAC SHA256 with your OA Secret Key to prevent spoofed requests.

---

## Reference Links

- Webhook events: https://developers.zalo.me/docs/official-account/webhook/tin-nhan/su-kien-nguoi-dung-gui-tin-nhan
- Upload image API: https://developers.zalo.me/docs/official-account/tin-nhan/quan-ly-tin-nhan/upload-hinh-anh
- Upload file API: https://developers.zalo.me/docs/official-account/tin-nhan/quan-ly-tin-nhan/upload-file
- Send message with image: https://developers.zalo.me/docs/api/official-account-api/gui-tin-va-thong-bao-qua-oa/v3/tin-tu-van/gui-tin-tu-van-dinh-kem-hinh-anh-post-7133
- Send message with file: https://developers.zalo.me/docs/api/official-account-api/gui-tin-va-thong-bao-qua-oa/v3/tin-tu-van/gui-tin-tu-van-dinh-kem-file-post-7137
