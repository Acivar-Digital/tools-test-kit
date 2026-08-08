# Gold E2E Multi-Channel & Concurrency Architecture

This document defines the architectural standard for running concurrent live execution, WhatsApp channels, and automated Gold E2E tests without configuration drift or disk side-effects.

---

## 1. Core Principles

1. **Pristine Configuration File**: `admin/controls/controls.py` is sacrosanct. It must never be modified on disk or physically swapped during test runs.
2. **Single Server Instance**: A single web server instance (`start2.py`) handles all incoming traffic (Production Telegram, WhatsApp, and UAT test webhooks).
3. **Session Partitioning**: Concurrency is managed at the database level. Sessions are partitioned by a combination of `platform` and `platform_user_id`.

---

## 2. Request Routing & Webhook Topology

Incoming webhook requests are routed through a Cloudflare Tunnel to the local FastAPI port (`8443` or `8445`).

```
                    ┌──────────────────────────┐
                    │    Cloudflare Tunnel     │
                    └────────────┬─────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
  [POST /webhook]     [POST /webhook/whatsapp]    [POST /webhook/test]
  Telegram Webhook        WhatsApp Webhook          Test Runner Webhook
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │    FastAPI Web Server    │
                    │       (start2.py)        │
                    └────────────┬─────────────┘
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │    Intake Coordinator    │
                    └────────────┬─────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
  Session Account         Session Account         Session Account
   platform: telegram      platform: whatsapp      platform: telegram_test
   puid: chat_id           puid: phone_number      puid: test_chat_id
```

---

## 3. Database Concurrency & Isolation

* **Concurrency Control**: Multiple incoming webhooks are handled concurrently via FastAPI's async event loop.
* **Write Locks**: SQLite or PostgreSQL manages concurrent database updates. 
* **User Isolation**: Because `telegram`, `whatsapp`, and `telegram_test` accounts possess unique platform identifiers and keys, User A (Telegram) and the UAT Test Runner (simulating User B) can converse with the bot concurrently without mutating or reading each other's session states.

---

## 4. Execution Workflow

### A. Live Bot Server
Run the bot locally in production mode:
```bash
uv run start2.py
```

### B. Concurrent Gold E2E Testing
Run the test runner directly against the running bot instance without spawning a sub-server or modifying disk files:
```bash
# baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'. --no-start-server --server-url http://127.0.0.1:8443
```
* `--no-start-server`: Instructs the runner to bypass local startup and directory modification.
* `--server-url`: Tells the runner to route all tests to the active port.
