  # SocketMock

  ![CI](https://github.com/wpeterw/SocketMock/actions/workflows/quality.yml/badge.svg)
  ![Coverage](https://img.shields.io/badge/coverage-20%25-red)
  ![Gitleaks](https://github.com/wpeterw/SocketMock/actions/workflows/gitleaks.yml/badge.svg)
  ![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

  SocketMock is a protocol simulator for non-HTTP services. It listens on a TCP port
  like a real service, but you drive its behavior through a REST admin API instead
  of hand-rolling test infrastructure. Configure stub responses, watch a request
  journal, and trigger protocol-specific events on demand.

  The core runtime is plugin-based: built-in plugins such as `smpp` and `sftp`
  implement protocol behavior, while new plugins can be added by creating a new
  package under `SocketMock/plugins/<protocol>/`. The registry discovers plugin
  packages automatically, so contributors do not need to edit a central registry
  file when they add a new protocol.

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
  uv run python -m SocketMock.app --port 2775 --admin-port 8080
  ```

  Optional authentication:

  ```bash
  uv run python -m SocketMock.app --credential loadtest:secret --credential otheruser:pw2
  ```

  Use a specific plugin when you add one:

  ```bash
  uv run python -m SocketMock.app --protocol smpp --port 2775 --admin-port 8080
  ```

  ## Concepts

  - **Protocol plugin**: a small adapter that knows how to turn a TCP connection into
  a mock session for a protocol.
  - **Admin port** (default 8080): JSON REST API under `/__admin` for mappings,
    request history, and reset operations.
  - **Protocol awareness**: the admin API is not a separate plugin registry. When
    the app starts, `SocketMock/app.py` resolves the selected `--protocol`, creates
    that plugin and its store, and then wires the admin app to that active plugin.
    The routes are generic, but the current protocol name/description and the active
    session store come from the plugin chosen at startup.
  - **Stub mapping**: a rule that matches incoming requests to a canned response,
    optionally including async follow-up behavior.

  ## Adding a new protocol

  The easiest path is to copy the starter template in `SocketMock/plugins/_template/`
  and adapt it to your protocol:

  1. Create a new directory under `SocketMock/plugins/<protocol>/`.
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

  - `SocketMock/plugins/` — protocol plugin packages and registry
  - `SocketMock/server.py` — asyncio TCP server core
  - `SocketMock/admin.py` — aiohttp admin REST API
  - `SocketMock/app.py` — CLI entry point wiring both servers together
  - `SocketMock/static/` — the dashboard (`index.html`, `app.css`, `app.js`), served by the admin app
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

