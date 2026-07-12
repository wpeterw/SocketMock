import asyncio
import sys
from typing import Any

sys.path.insert(0, ".")
from SocketMock.plugins.smpp import codec as pdumod


async def main() -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", 2776)

    async def send(pdu: dict[str, Any]) -> None:
        writer.write(pdumod.encode_pdu(pdu))
        await writer.drain()

    async def recv() -> dict[str, Any]:
        buf = bytearray()
        while True:
            chunk = await reader.read(4096)
            buf.extend(chunk)
            pdu, consumed = pdumod.try_extract_one(buf)
            if consumed:
                del buf[:consumed]
                if pdu is None:
                    raise RuntimeError("failed to decode PDU")
                return pdu

    await send(
        {
            "command_name": "bind_transceiver",
            "sequence_number": 1,
            "system_id": "loadtest",
            "password": "secret",
            "interface_version": 0x34,
        }
    )
    print("bind_resp:", await recv())

    await send(
        {
            "command_name": "submit_sm",
            "sequence_number": 2,
            "source_addr": "254700000000",
            "destination_addr": "447700900000",
            "short_message": "HELLO PROMO CODE",
        }
    )
    print("submit_sm_resp:", await recv())

    receipt = await recv()
    print("deliver_sm (receipt):", receipt)

    await send(
        {
            "command_name": "deliver_sm_resp",
            "sequence_number": receipt["sequence_number"],
            "message_id": "",
        }
    )

    await send(
        {
            "command_name": "submit_sm",
            "sequence_number": 3,
            "source_addr": "111",
            "destination_addr": "222",
            "short_message": "unmatched traffic",
        }
    )
    print("submit_sm_resp (unmatched):", await recv())

    await send({"command_name": "enquire_link", "sequence_number": 4})
    print("enquire_link_resp:", await recv())

    await send({"command_name": "unbind", "sequence_number": 5})
    print("unbind_resp:", await recv())

    writer.close()


if __name__ == "__main__":
    asyncio.run(main())
