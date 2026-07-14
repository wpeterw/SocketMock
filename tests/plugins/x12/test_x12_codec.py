from socketmock.plugins.x12.codec import decode_message, encode_ack


def test_x12_codec_helpers() -> None:
    payload = (
        b"ISA*00*          *00*          *01*SENDER*01*RECEIVER*240101*0101*"
        b"U*00401*000000001*0*P*:~"
    )
    decoded = decode_message(payload)

    assert decoded["isa"]["control_id"] == "000000001"
    assert decoded["isa"]["sender"] == "SENDER"

    ack = encode_ack(decoded)
    assert b"AK9" in ack
    assert b"000000001" in ack
