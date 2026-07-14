from socketmock.plugins.hl7v2.codec import decode_message, encode_ack, frame_message


def test_hl7v2_codec_helpers() -> None:
    payload = (
        "MSH|^~\\&|APP|FAC|OTHER|FAC2|20240101120000||ADT^A01|12345|P|2.4\r"
        "PID|1"
    )
    framed = frame_message(payload)
    decoded = decode_message(framed)

    assert decoded is not None
    assert decoded["message_type"] == "ADT^A01"
    assert decoded["msh"]["sending_app"] == "APP"

    ack = encode_ack(decoded)
    assert b"MSA|AA|12345" in ack
