from socketmock.plugins.iso8583.codec import decode_message, encode_response


def test_iso8583_codec_round_trip() -> None:
    encoded = encode_response({"mti": "0200", "fields": {11: b"123456", 37: b"ABC"}})
    decoded = decode_message(encoded)

    assert decoded is not None
    assert decoded["mti"] == "0210"
    assert decoded["fields"][11] == b"123456"
    assert decoded["fields"][37] == b"ABC"
    assert decoded["fields"][39] == b"00"
