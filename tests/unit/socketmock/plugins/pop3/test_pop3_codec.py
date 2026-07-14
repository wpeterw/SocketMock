from socketmock.plugins.pop3.codec import POP3Codec, POP3Message


def test_pop3_codec_helpers() -> None:
    assert POP3Codec.parse_command("USER alice") == ("USER", "alice")
    assert POP3Codec.build_ok("ok") == "+OK ok"
    assert POP3Codec.build_err("bad") == "-ERR bad"
    assert POP3Codec.build_stat(2, 10) == "+OK 2 10"

    message = POP3Message(uid=1, size=5, body="hello")
    assert POP3Codec.serialize_message(message) == "hello"
