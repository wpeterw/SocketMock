"""
Entry point: starts the mock TCP server and the admin HTTP API together.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

from aiohttp import web

from .admin import make_admin_app
from .plugins import ProtocolRegistry
from .server import ProtocolServer


def parse_args() -> argparse.Namespace:
    available_protocols = ProtocolRegistry.available()
    default_protocol = available_protocols[0] if available_protocols else "smpp"
    p = argparse.ArgumentParser(description="Protocol-agnostic mock simulator")
    p.add_argument(
        "--protocol",
        default=default_protocol,
        choices=available_protocols,
        help="protocol plugin to run",
    )
    p.add_argument("--host", default="0.0.0.0", help="host for the protocol server")
    p.add_argument("--port", type=int, default=2775, help="port for the protocol server")
    p.add_argument("--admin-host", default="0.0.0.0")
    p.add_argument("--admin-port", type=int, default=8080)
    p.add_argument(
        "--system-id",
        default="socketmock",
        help="identifier reported by the selected protocol plugin",
    )
    p.add_argument(
        "--require-auth",
        action="store_true",
        help="reject binds unless --credential user:pass given at least once",
    )
    p.add_argument(
        "--credential",
        action="append",
        default=[],
        help="user:pass pair accepted at bind time; repeatable",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    creds: dict[str, str] | None = None
    if args.credential:
        creds = {}
        for pair in args.credential:
            user, _, pw = pair.partition(":")
            creds[user] = pw
    elif args.require_auth:
        creds = {}

    plugin = ProtocolRegistry.get(args.protocol)
    if plugin is None:
        raise SystemExit(f"unknown protocol: {args.protocol}")

    store = plugin.create_store()
    config: dict[str, Any] = {"system_id": args.system_id, "credentials": creds}

    server = ProtocolServer(store, plugin=plugin, host=args.host, port=args.port, config=config)
    await server.start()

    admin_app = make_admin_app(
        store, protocol_name=plugin.name, protocol_description=plugin.description
    )
    runner = web.AppRunner(admin_app)
    await runner.setup()
    site = web.TCPSite(runner, args.admin_host, args.admin_port)
    await site.start()
    logging.getLogger("SocketMock").info(
        "Admin API listening on http://%s:%s/__admin", args.admin_host, args.admin_port
    )

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
