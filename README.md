  # SocketMock

  ![CI](https://github.com/wpeterw/SocketMock/actions/workflows/quality.yml/badge.svg)
  ![Coverage](./.github/badges/coverage.svg)
  ![Gitleaks](https://github.com/wpeterw/SocketMock/actions/workflows/gitleaks.yml/badge.svg)
  ![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

  SocketMock is a protocol simulator for non-HTTP services. It listens on a TCP port
  like a real service, but you drive its behavior through a REST admin API instead
  of hand-rolling test infrastructure. Configure stub responses, watch a request
  journal, and trigger protocol-specific events on demand.

  The core runtime is plugin-based: built-in plugins such as `smpp`, `sftp`,
  `hl7v2`, `x12`, `iso8583`, `smtp`, `pop3`, and `imap` implement protocol
  behavior, while new plugins can be added by creating a new package under
  `socketmock/plugins/<protocol>/`. The registry discovers plugin packages
  automatically, so contributors do not need to edit a central registry file
  when they add a new protocol.

  ## Run it with Docker

  ```bash
  docker compose up --build
  ```
  Then point a client at `localhost:2775` and open the dashboard at
  `http://localhost:8080/`. Stub mappings and the request journal live in memory,
  so they reset whenever the container restarts.

  To require authentication or change flags, adjust the `command:` block in
  `docker-compose.yml`, for example:

  ```yaml
  command: >
    --host 0.0.0.0 --port 2775
    --admin-host 0.0.0.0 --admin-port 8080
    --credential loadtest:secret
  ```

  ## Run it without Docker

  ```bash
  uv sync --group dev
  uv run python -m socketmock.app --port 2775 --admin-port 8080
  ```

  Auth-capable protocols accept any credentials supplied by a client. You can still
  pass explicit credentials at startup if you want to document them in your test setup:

  ```bash
  uv run python -m socketmock.app --credential loadtest:secret --credential otheruser:pw2
  ```

  Use a specific plugin when you add one:

  ```bash
  uv run python -m socketmock.app --protocol smpp --port 2775 --admin-port 8080
  ```

  ## Built-in protocol plugins

  All built-in plugins are started the same way; only the protocol name and port change:

  ```bash
  uv run python -m socketmock.app --protocol <name> --port <port> --admin-port 8080
  ```

  ### SMPP

  - Protocol: SMPP 3.4-style messaging over TCP.
  - Capabilities: binds (`bind_transceiver`, `bind_receiver`, `bind_transmitter`), submits messages with `submit_sm`, answers `enquire_link`, and can emit simulated delivery receipts when a stub requests them.
  - Limitations: this is a mock transport, not a full SMSC; it does not implement the full SMPP feature set, optional TLVs, or real message delivery.
  - How to use it: start with `--protocol smpp` (default port `2775`) and send PDUs from a client; use the admin API to inspect sessions and stub responses.

  ### SFTP

  - Protocol: SSH File Transfer Protocol packets.
  - Capabilities: supports SSH_FXP_INIT, open/close/read/write, directory operations, stat/lstat/setstat/remove/mkdir/rmdir, and realpath against a local filesystem root.
  - Limitations: it is not a full SSH server and does not implement the complete SFTP extension set or real authentication/permissions.
  - How to use it: start with `--protocol sftp` (default port `2222`); connect with an SFTP client or a test harness that speaks the binary packet format.

  ### HL7 v2

  - Protocol: HL7 v2 over MLLP framing.
  - Capabilities: accepts framed HL7 messages and returns a simple ACK (`MSA|AA|...`) with the original control ID.
  - Limitations: this is a lightweight mock parser; it does not provide full HL7 validation, segment libraries, or real workflow routing.
  - How to use it: start with `--protocol hl7v2` (default port `2776`) and send MLLP-framed HL7 payloads from a client.

  ### X12 EDI

  - Protocol: X12 EDI over a plain TCP stream.
  - Capabilities: parses transaction messages terminated by `~` and responds with a basic 997 functional acknowledgement.
  - Limitations: it does not implement full X12 transaction set validation or every possible segment variant.
  - How to use it: start with `--protocol x12` (default port `2777`) and send X12 payloads from a client or test harness.

  ### ISO 8583

  - Protocol: ISO 8583 length-prefixed binary messages.
  - Capabilities: decodes ISO 8583 messages, returns a protocol response with a response MTI, and preserves common fields such as `11`, `12`, `37`, and `39`.
  - Limitations: it is a protocol mock, not a payment processor; it does not perform real card validation, switching, or full field-level processing.
  - How to use it: start with `--protocol iso8583` (default port `2778`) and send framed ISO 8583 messages from a client.

  ### SMTP

  - Protocol: SMTP command-response conversations.
  - Capabilities: supports `HELO`/`EHLO`, `AUTH`, `MAIL FROM`, `RCPT TO`, `DATA`, `RSET`, `NOOP`, and `QUIT`, and collects messages in memory for later inspection.
  - Limitations: it does not deliver mail externally, does not implement the full SMTP command set, and does not offer real queueing or relay behavior.
  - How to use it: start with `--protocol smtp` (default port `2779`) and talk to it with a mail client or raw TCP client.

  ### POP3

  - Protocol: POP3 mailbox access over TCP.
  - Capabilities: supports `USER`, `PASS`, `STAT`, `LIST`, `RETR`, `DELE`, `RSET`, `NOOP`, and `QUIT` with an in-memory mailbox and delete/undelete semantics.
  - Limitations: it is a simple mailbox mock, not a full mail server; mailbox contents reset with the process and there is no real message persistence or server-side storage.
  - How to use it: start with `--protocol pop3` (default port `2780`) and interact with it using a POP3 client or a raw socket.

  ### IMAP

  - Protocol: IMAP mailbox access over TCP.
  - Capabilities: supports `LOGIN`, `CAPABILITY`, `LIST`, `SELECT`, `FETCH`, `EXPUNGE`, `CLOSE`, `NOOP`, and `LOGOUT` with a simple in-memory mailbox.
  - Limitations: it is a lightweight IMAP mock and does not implement the full IMAP command grammar, server state model, or real mailbox syncing.
  - How to use it: start with `--protocol imap` (default port `2781`) and talk to it with an IMAP client or raw TCP client.

  ## Concepts

  - **Protocol plugin**: a small adapter that knows how to turn a TCP connection into
  a mock session for a protocol.
  - **Admin port** (default 8080): JSON REST API under `/__admin` for mappings,
    request history, and reset operations.
  - **Protocol awareness**: the admin API is not a separate plugin registry. When
    the app starts, `socketmock/app.py` resolves the selected `--protocol`, creates
    that plugin and its store, and then wires the admin app to that active plugin.
    The routes are generic, but the current protocol name/description and the active
    session store come from the plugin chosen at startup.
  - **Stub mapping**: a rule that matches incoming requests to a canned response,
    optionally including async follow-up behavior.

  ## Adding a new protocol

  The easiest path is to copy the starter template in `socketmock/plugins/_template/`
  and adapt it to your protocol:

  1. Create a new directory under `socketmock/plugins/<protocol>/`.
  2. Implement a `ProtocolPlugin` subclass in `plugin.py` and a `ProtocolSession`
     subclass in `session.py`.
  3. Add a `stubs.py` module if you need protocol-specific matching; otherwise the
     shared `libs/stubs` store is already available.
  4. Put any wire-format helpers in `codec.py`.
  5. Register the plugin from `__init__.py` using `ProtocolRegistry.register(...)`.

  No central registry edit is required: `ProtocolRegistry.discover()` imports every
  plugin package automatically, so `--protocol <protocol>` will work as soon as the
  new package is present.

  ## Dashboard

  Open **http://localhost:8080/** (the admin port) for a live console: bound
  sessions on the left, a scrolling traffic trace in the middle, and stub mappings
  on the right with a form to create new ones. It is a thin client over the same
  `/__admin` API, polling regularly so anything you do via curl shows up there too.

  ## Admin API

  The admin API is protocol-agnostic at the route level, but it is attached to the
  plugin selected when the process starts. In practice, that means `/__admin/health`
  reports the active protocol, and `/__admin/deliver` works against the active
  plugin's session/store model for that run.

  | Method | Path                     | Purpose                                   |
  |--------|--------------------------|--------------------------------------------|
  | POST   | `/__admin/mappings`      | create a stub mapping                      |
  | GET    | `/__admin/mappings`      | list mappings                              |
  | GET    | `/__admin/mappings/{id}` | get one mapping                            |
  | DELETE | `/__admin/mappings/{id}` | delete one mapping                         |
  | DELETE | `/__admin/mappings`      | clear all mappings                         |
  | GET    | `/__admin/requests`      | request/response journal                   |
  | DELETE | `/__admin/requests`      | clear the journal                          |
  | POST   | `/__admin/reset`         | clear mappings + journal                   |
  | GET    | `/__admin/sessions`      | list currently bound SocketMock sessions   |
  | POST   | `/__admin/deliver`       | push a protocol-specific event to a session |
  | GET    | `/__admin/health`        | liveness check                             |

  ### Create a stub

  ```bash
  curl -X POST http://localhost:8080/__admin/mappings -H 'Content-Type: application/json' -d '{
    "priority": 1,
    "request": {
      "operation": "open",
      "path": {"contains": "/tmp"}
    },
    "response": {
      "statusCode": 0,
      "message": "ok"
    }
  }'
  ```

  ### Inspect traffic

  ```bash
  curl http://localhost:8080/__admin/requests
  ```

  ## Files

  - `socketmock/plugins/` — protocol plugin packages and registry
  - `socketmock.server.py` — asyncio TCP server core
  - `socketmock.admin.py` — aiohttp admin REST API
  - `socketmock/app.py` — CLI entry point wiring both servers together
  - `socketmock/static/` — the dashboard (`index.html`, `app.css`, `app.js`), served by the admin app
  - `Dockerfile`, `docker-compose.yml`, `.dockerignore` — containerized run

  ## Development

  ```bash
  uv sync --group dev
  uv run ruff check .
  uv run ruff format .
  uv run ty check .
  uv run pytest --cov=socketmock --cov-report=term-missing
  ```

  The GitHub Actions workflow runs the same checks automatically on pushes and pull requests.

