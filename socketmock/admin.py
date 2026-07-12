"""
Admin REST API with a simple /__admin surface for managing mappings, requests, and sessions.
"""

from __future__ import annotations

import pathlib
import time

from aiohttp import web

from libs.stubs import StubStore

from .plugins import ProtocolStubStore

STATIC_DIR = pathlib.Path(__file__).parent / "static"


def make_admin_app(
    store: ProtocolStubStore,
    protocol_name: str = "socketmock",
    protocol_description: str = "mock protocol service",
) -> web.Application:
    app = web.Application()
    app["store"] = store
    app["protocol_name"] = protocol_name
    app["protocol_description"] = protocol_description

    app.router.add_get("/", index)
    app.router.add_static("/static/", path=STATIC_DIR, name="static")

    app.router.add_post("/__admin/mappings", create_mapping)
    app.router.add_get("/__admin/mappings", list_mappings)
    app.router.add_get("/__admin/mappings/{id}", get_mapping)
    app.router.add_delete("/__admin/mappings/{id}", delete_mapping)
    app.router.add_delete("/__admin/mappings", reset_mappings)

    app.router.add_get("/__admin/requests", list_requests)
    app.router.add_delete("/__admin/requests", reset_requests)

    app.router.add_get("/__admin/sessions", list_sessions)
    app.router.add_post("/__admin/deliver", deliver_now)

    app.router.add_post("/__admin/reset", reset_all)
    app.router.add_get("/__admin/health", health)

    return app


async def index(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def health(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "ok",
            "time": time.time(),
            "protocol": request.app.get("protocol_name", "socketmock"),
            "protocolDescription": request.app.get("protocol_description", "mock protocol service"),
        }
    )


async def create_mapping(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "JSON body must be an object"}, status=400)
    if "request" not in body:
        return web.json_response({"error": "'request' field is required"}, status=400)
    stub = store.add(body)
    return web.json_response(stub.to_dict(), status=201)


async def list_mappings(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    return web.json_response({"mappings": store.list()})


async def get_mapping(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    stub = store.get(request.match_info["id"])
    if not stub:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(stub)


async def delete_mapping(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    ok = store.delete(request.match_info["id"])
    if not ok:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"deleted": True})


async def reset_mappings(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    store.reset_mappings()
    return web.json_response({"reset": True})


async def list_requests(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    return web.json_response({"requests": store.journal()})


async def reset_requests(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    store.reset_journal()
    return web.json_response({"reset": True})


async def reset_all(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    store.reset_all()
    return web.json_response({"reset": True})


async def list_sessions(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    return web.json_response({"sessions": store.list_sessions()})


async def deliver_now(request: web.Request) -> web.Response:
    store: StubStore = request.app["store"]
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "JSON body must be an object"}, status=400)

    session_id = body.get("sessionId")
    handle = store.get_session_handle(session_id) if session_id else None
    if handle is None:
        return web.json_response({"error": f"no bound session '{session_id}'"}, status=404)

    deliver_pdu = {
        "command_name": "deliver_sm",
        "sequence_number": handle.next_seq(),
        "command_status": 0,
        "service_type": "",
        "source_addr_ton": body.get("sourceAddrTon", 0),
        "source_addr_npi": body.get("sourceAddrNpi", 0),
        "source_addr": body.get("sourceAddr", ""),
        "dest_addr_ton": body.get("destAddrTon", 0),
        "dest_addr_npi": body.get("destAddrNpi", 0),
        "destination_addr": body.get("destinationAddr", ""),
        "esm_class": body.get("esmClass", 0),
        "protocol_id": 0,
        "priority_flag": 0,
        "registered_delivery": 0,
        "data_coding": body.get("dataCoding", 0),
        "short_message": body.get("shortMessage", ""),
    }
    await handle.send(deliver_pdu)
    store.log_request(
        {
            "sessionId": session_id,
            "direction": "out",
            "commandName": "deliver_sm",
            "sequenceNumber": deliver_pdu["sequence_number"],
            "timestamp": time.time(),
            "pdu": {"short_message": deliver_pdu["short_message"]},
            "triggeredBy": "admin",
        }
    )
    return web.json_response({"sent": True, "sequenceNumber": deliver_pdu["sequence_number"]})
