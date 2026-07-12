# SocketMock

![CI](https://github.com/wpeterw/SocketMock/actions/workflows/quality.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-20%25-red)

A Wiremock-style simulator for non-HTTP protocols, starting with SocketMock (v3.4).
It listens like a real service on a TCP port, but you drive its behavior through
a REST admin API instead of hand-rolling test infrastructure — configure stub
responses, watch a request journal, and trigger protocol-specific events on demand.

The core runtime is now protocol-plugin based: the built-in `socketmock` plugin keeps
all current SocketMock behavior, while new plugins can be registered by implementing a
small `ProtocolPlugin` interface and exposing it through the registry.

## Run it with Docker

```bash
docker compose up --build
```
Then point your SocketMock client at `localhost:2775` and open the dashboard at
`http://localhost:8080/`. Stub mappings and the request journal live in memory,
so they reset whenever the container restarts.

To require bind auth or change flags, uncomment and edit the `command:` block
in `docker-compose.yml`, e.g.:
```yaml
command: >
  --host 0.0.0.0 --port 2775
  --admin-host 0.0.0.0 --admin-port 8080
  --credential loadtest:secret
```

## Run it without Docker

```bash
pip install -r requirements.txt
python -m SocketMock.app --port 2775 --admin-port 8080
```
Optional bind auth:
```bash
python -m SocketMock.app --credential loadtest:secret --credential otheruser:pw2
```
If `--credential` is never given, any `system_id`/`password` is accepted (the default,
convenient for local dev).

Use a different plugin when you add one:
```bash
python -m SocketMock.app --protocol socketmock --port 2775 --admin-port 8080
```

## Concepts

- **Protocol plugin**: a small adapter that knows how to turn a TCP connection into
  a mock session for a protocol. The built-in `socketmock` plugin covers the current
  behavior.
- **SocketMock port** (default 2775): real SocketMock protocol, TCP, binary PDUs. Point your
  ESME/client at this like any SMSC.
- **Admin port** (default 8080): JSON REST API under `/__admin`, same shape as
  Wiremock's `/__admin` — mappings, requests journal, reset.
- **Stub mapping**: a rule matching incoming PDUs (by command type and fields like
  `sourceAddr`/`destinationAddr`/`shortMessage`) to a canned response, optionally
  including an asynchronous delivery receipt.
- Unmatched `submit_sm` traffic still gets a default `ESME_ROK` + random
  `message_id` so a client isn't left hanging — it's just logged with
  `matchedStubId: null` so you can tell it apart in the journal.

## Dashboard

Open **http://localhost:8080/** (the admin port) for a live console: bound
sessions on the left, a scrolling PDU trace in the middle (click any row for
the full decoded PDU), and stub mappings on the right with a form to create
new ones — no need to hand-write curl/JSON unless you want to. There's also a
quick form to push an ad-hoc `deliver_sm` (MO or receipt) into any bound
session. It's a thin client over the same `/__admin` API below, polling every
1.2s, so anything you do via curl shows up there too.

## Admin API

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
| GET    | `/__admin/sessions`      | list currently bound SocketMock sessions         |
| POST   | `/__admin/deliver`       | push an ad-hoc `deliver_sm` to a session   |
| GET    | `/__admin/health`        | liveness check                             |

### Create a stub

```bash
curl -X POST http://localhost:8080/__admin/mappings -H 'Content-Type: application/json' -d '{
  "priority": 1,
  "request": {
    "commandName": "submit_sm",
    "shortMessage": {"contains": "PROMO"}
  },
  "response": {
    "commandStatus": 0,
    "messageId": "sim-{{randomId}}",
    "delayMs": 50,
    "deliveryReceipt": {
      "enabled": true,
      "delayMs": 2000,
      "finalStatus": "DELIVRD"
    }
  }
}'
```

Matchers on `sourceAddr`, `destinationAddr`, `shortMessage`, `serviceType`, `systemId`
support: `equalTo`, `contains`, `regex` (alias `matches`), `absent`. Lower `priority`
number wins when multiple stubs match, same as Wiremock.

`finalStatus` accepts `DELIVRD`, `UNDELIV`, `EXPIRED`, `DELETED`, `ACCEPTD`, `REJECTD`, `UNKNOWN`.

### Simulate an error response (e.g. throttling)

```bash
curl -X POST http://localhost:8080/__admin/mappings -H 'Content-Type: application/json' -d '{
  "request": {"commandName": "submit_sm", "destinationAddr": {"contains": "999"}},
  "response": {"commandStatus": 88}
}'
```
(`88` = `ESME_RTHROTTLED`; use whichever SocketMock status code you need to reproduce.)

### Trigger an MO or delivery receipt manually

```bash
curl -X POST http://localhost:8080/__admin/deliver -H 'Content-Type: application/json' -d '{
  "sessionId": "sess-1",
  "sourceAddr": "254700000000",
  "destinationAddr": "447700900000",
  "shortMessage": "Inbound test message"
}'
```
Get `sessionId` from `GET /__admin/sessions`.

### Inspect traffic

```bash
curl http://localhost:8080/__admin/requests
```
Every inbound and outbound PDU is logged with a timestamp, session id, and
(for `submit_sm_resp`) which stub matched.

## What's implemented

Core SocketMock v3.4 lifecycle: `bind_transmitter` / `bind_receiver` / `bind_transceiver`
(+ resp), `submit_sm` (+ resp), `deliver_sm` (+ resp), `enquire_link` (+ resp),
`unbind` (+ resp), `generic_nack`. TLVs on `submit_sm`/`deliver_sm` are parsed
and preserved but not matched on by default.

Not implemented: `submit_multi`, `query_sm`, `replace_sm`, `cancel_sm`,
`data_sm`, `outbind`, TLS. These are straightforward to add in `pdu.py` and
`server.py` following the existing patterns if you need them.

## Files

- `SocketMock/plugins/` — protocol plugin package (base interface + registry)
- `SocketMock/plugins/socketmock/pdu.py` — PDU encode/decode for the built-in socketmock plugin
- `SocketMock/plugins/socketmock/stubs.py` — stub matching engine + request journal + session registry for the built-in socketmock plugin
- `SocketMock/server.py` — asyncio TCP server core + built-in SocketMock session state machine
- `SocketMock/admin.py` — aiohttp admin REST API
- `SocketMock/app.py` — CLI entry point wiring both servers together
- `SocketMock/static/` — the dashboard (`index.html`, `app.css`, `app.js`), served by the admin app
- `test_client.py` — example raw SocketMock client exercising bind/submit/receipt/unbind
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` — containerized run

## Development

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format .
uv run ty check .
uv run pytest --cov=SocketMock --cov-report=term-missing
```

The GitHub Actions workflow runs the same checks automatically on pushes and pull requests.

