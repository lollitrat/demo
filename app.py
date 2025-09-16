import os
import requests
from flask import Flask, request
from dotenv import load_dotenv

# Load .env
load_dotenv()

app = Flask(__name__)

# Environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")  # Messenger Page token
PAGE_ID = os.getenv("PAGE_ID")  # Messenger Page ID

VOICEFLOW_API_KEY = os.getenv("VOICEFLOW_API_KEY")
VOICEFLOW_VERSION_ID = os.getenv("VOICEFLOW_VERSION_ID")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "voiceflow123")

# ✅ Webhook verification (shared for WhatsApp + Messenger)
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified")
        return challenge, 200
    return "Forbidden", 403


# ✅ Webhook receiver
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Incoming webhook payload:", data)

    try:
        if "object" in data:
            # WhatsApp handler
            if data["object"] == "whatsapp_business_account":
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        value = change.get("value", {})
                        if "messages" in value:
                            for message in value["messages"]:
                                user_id = message["from"]
                                user_text = message.get("text", {}).get("body", "")
                                print(f"👉 WhatsApp message from {user_id}: {user_text}")

                                handle_voiceflow_and_reply(user_id, user_text, platform="whatsapp")

            # Messenger handler
            elif data["object"] == "page":
                for entry in data.get("entry", []):
                    for messaging_event in entry.get("messaging", []):
                        sender_id = messaging_event.get("sender", {}).get("id")
                        message_text = messaging_event.get("message", {}).get("text")

                        if sender_id and message_text:
                            print(f"👉 Messenger message from {sender_id}: {message_text}")
                            handle_voiceflow_and_reply(sender_id, message_text, platform="messenger")

    except Exception as e:
        print("❌ ERROR in webhook:", str(e))

    return "EVENT_RECEIVED", 200


# ✅ Helper function: Forward to Voiceflow and send reply
def handle_voiceflow_and_reply(user_id, user_text, platform="whatsapp"):
    try:
        # Send to Voiceflow
        vf_response = requests.post(
            f"https://general-runtime.voiceflow.com/state/user/{user_id}/interact",
            headers={
                "Authorization": VOICEFLOW_API_KEY,
                "Content-Type": "application/json"
            },
            json={"action": {"type": "text", "payload": user_text}}
        )

        print("🔵 Voiceflow status:", vf_response.status_code)
        print("🔵 Voiceflow raw response:", vf_response.text)

        if vf_response.status_code == 200:
            reply_data = vf_response.json()
            bot_replies = []

            for item in reply_data:
                if item.get("type") == "text":
                    msg = item.get("payload", {}).get("message")
                    if msg:
                        bot_replies.append(msg)

            if not bot_replies:
                print("⚠️ No text replies found from Voiceflow")
            else:
                for bot_reply in bot_replies:
                    print(f"🤖 Replying on {platform} to {user_id}: {bot_reply}")
                    send_message(user_id, bot_reply, platform)

    except Exception as e:
        print("❌ Error in handle_voiceflow_and_reply:", str(e))


# ✅ Send message (WhatsApp or Messenger)
def send_message(user_id, text, platform="whatsapp"):
    if platform == "whatsapp":
        wa_response = requests.post(
            f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages",
            headers={
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "messaging_product": "whatsapp",
                "to": user_id,
                "type": "text",
                "text": {"body": text}
            }
        )
        print("🟢 WhatsApp status:", wa_response.status_code)
        print("🟢 WhatsApp response:", wa_response.text)

    elif platform == "messenger":
        ms_response = requests.post(
            f"https://graph.facebook.com/v17.0/me/messages",
            params={"access_token": PAGE_ACCESS_TOKEN},
            headers={"Content-Type": "application/json"},
            json={
                "recipient": {"id": user_id},
                "message": {"text": text}
            }
        )
        print("🟢 Messenger status:", ms_response.status_code)
        print("🟢 Messenger response:", ms_response.text)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
