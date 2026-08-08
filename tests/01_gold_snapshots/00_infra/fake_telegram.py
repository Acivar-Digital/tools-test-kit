#!/usr/env/bin python3
import logging

import uvicorn
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FakeTelegram")

app = FastAPI(title="Fake Telegram Server")

# Global list to store intercepted messages for the test runner to inspect
intercepted_messages = []

@app.get("/bot{token}/getMe")
async def mock_get_me(token: str):
    logger.info(f"Received getMe for token: {token[:5]}...")
    return {"ok": True, "result": {"username": "test_bot"}}

@app.get("/bot{token}/getWebhookInfo")
async def mock_get_webhook_info(token: str):
    logger.info(f"Received getWebhookInfo for token: {token[:5]}...")
    return {"ok": True, "result": {"url": "http://127.0.0.1:8445/webhook"}}

@app.post("/bot{token}/sendMessage")
async def mock_send_message(token: str, request: Request):
    payload = await request.json()
    chat_id = payload.get("chat_id")
    text = payload.get("text")
    logger.info(f"Intercepted sendMessage to {chat_id}: {text[:50]}...")

    # Save the intercepted message
    intercepted_messages.append({
        "chat_id": chat_id,
        "text": text,
        "raw_payload": payload
    })

    # Optional: write to a file for easy debugging
    with open("logs/intercepted_markdown.log", "a", encoding="utf-8") as f:
        f.write(f"--- TO: {chat_id} ---\n{text}\n\n")

    return {
        "ok": True,
        "result": {
            "message_id": 999999,
            "text": text
        }
    }

@app.get("/bot{token}/setWebhook")
async def mock_set_webhook_get(token: str):
    # Telegram allows setWebhook via GET query params sometimes
    logger.info(f"Received setWebhook for token: {token[:5]}...")
    return {"ok": True}

@app.post("/bot{token}/setWebhook")
async def mock_set_webhook_post(token: str):
    logger.info(f"Received setWebhook for token: {token[:5]}...")
    return {"ok": True}

@app.get("/intercepted")
async def get_intercepted():
    """Endpoint for the test runner to fetch all intercepted messages."""
    return {"messages": intercepted_messages}

@app.delete("/intercepted")
async def clear_intercepted():
    """Endpoint for the test runner to clear intercepted messages between tests."""
    intercepted_messages.clear()
    return {"status": "cleared"}

if __name__ == "__main__":
    logger.info("Starting Fake Telegram Server on port 9999...")
    # Make sure to clear the log file on startup
    with open("logs/intercepted_markdown.log", "w", encoding="utf-8") as f:
        f.write("=== FAKE TELEGRAM INTERCEPT LOG ===\n\n")
    uvicorn.run(app, host="127.0.0.1", port=9999)
